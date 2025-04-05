import os
import logging
import json
import tempfile
import warnings

import gradio as gr
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastrtc import (
    AdditionalOutputs,
    ReplyOnPause,
    Stream,
    AlgoOptions,
    SileroVadOptions,
    audio_to_bytes,
)
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
    pipeline,
)
from transformers.utils import is_flash_attn_2_available

from utils.logger_config import setup_logging
from utils.device import get_device, get_torch_and_np_dtypes
from utils.turn_server import get_rtc_credentials


setup_logging()
logger = logging.getLogger(__name__)

# Filter out specific transformers warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
warnings.filterwarnings("ignore", message=".*attention mask is not set.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*passed task=transcribe, but also have set.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Due to a bug fix in.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*forced_decoder_ids.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*inferred from input.*", category=UserWarning)
# Suppress all UserWarnings from transformers
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
# Suppress library INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)


# Define environment variables directly
SERVER_NAME = "localhost"
MODEL_ID = os.getenv("MODEL_ID", "openai/whisper-large-v3-turbo")


device = get_device(force_cpu=False)
torch_dtype, np_dtype = get_torch_and_np_dtypes(device, use_bfloat16=False)
logger.info(f"Using device: {device}, torch_dtype: {torch_dtype}, np_dtype: {np_dtype}")


attention = "flash_attention_2" if is_flash_attn_2_available() else "sdpa"
logger.info(f"Using attention: {attention}")

logger.info(f"Loading Whisper model: {MODEL_ID}")

try:
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_ID, 
        torch_dtype=torch_dtype, 
        low_cpu_mem_usage=True, 
        use_safetensors=True,
        attn_implementation=attention
    )
    model.to(device)
except Exception as e:
    logger.error(f"Error loading ASR model: {e}")
    logger.error(f"Are you providing a valid model ID? {MODEL_ID}")
    raise

processor = AutoProcessor.from_pretrained(MODEL_ID)

transcribe_pipeline = pipeline(
    task="automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch_dtype,
    device=device,
)

# Warm up the model with empty audio
logger.info("Warming up Whisper model with dummy input")
warmup_audio = np.zeros((16000,), dtype=np_dtype)  # 1s of silence
transcribe_pipeline(warmup_audio)
logger.info("Model warmup complete")


async def transcribe(audio: tuple[int, np.ndarray]):
    sample_rate, audio_array = audio
    logger.info(f"Sample rate: {sample_rate}Hz, Shape: {audio_array.shape}")
    
    outputs = transcribe_pipeline(
        audio_to_bytes(audio),
        chunk_length_s=3,
        batch_size=1,
        generate_kwargs={
            'task': 'transcribe',
            'language': 'english',
        },
        #return_timestamps="word"
    )
    yield AdditionalOutputs(outputs["text"].strip())


logger.info("Initializing FastRTC stream")
stream = Stream(
    handler=ReplyOnPause(
        transcribe,
        algo_options=AlgoOptions(
            # Duration in seconds of audio chunks (default 0.6)
            audio_chunk_duration=0.6,
            # If the chunk has more than started_talking_threshold seconds of speech, the user started talking (default 0.2)
            started_talking_threshold=0.2,
            # If, after the user started speaking, there is a chunk with less than speech_threshold seconds of speech, the user stopped speaking. (default 0.1)
            speech_threshold=0.1,
        ),
        model_options=SileroVadOptions(
            # Threshold for what is considered speech (default 0.5)
            threshold=0.5,
            # Final speech chunks shorter min_speech_duration_ms are thrown out (default 250)
            min_speech_duration_ms=250,
            # Max duration of speech chunks, longer will be split (default float('inf'))
            max_speech_duration_s=30,
            # Wait for ms at the end of each speech chunk before separating it (default 2000)
            min_silence_duration_ms=2000,
            # Chunk size for VAD model. Can be 512, 1024, 1536 for 16k s.r. (default 1024)
            window_size_samples=1024,
            # Final speech chunks are padded by speech_pad_ms each side (default 400)
            speech_pad_ms=400,
        ),
    ),
    # send-receive: bidirectional streaming (default)
    # send: client to server only
    # receive: server to client only
    modality="audio",
    mode="send",
    additional_outputs=[
        gr.Textbox(label="Transcript"),
    ],
    additional_outputs_handler=lambda current, new: current + " " + new,
    rtc_configuration=None  # Simplified for local mode
)

app = FastAPI()
stream.mount(app)

@app.get("/")
async def index():
    html_content = open("index.html", encoding="utf-8").read()
    rtc_config = None  # Simplified for local mode
    return HTMLResponse(content=html_content.replace("__RTC_CONFIGURATION__", json.dumps(rtc_config)))

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Handle uploaded audio files and transcribe them."""
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            # Read chunks from uploaded file and write to temp file
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Process the audio file with the transcription pipeline
        logger.info(f"Transcribing uploaded file: {file.filename}")
        outputs = transcribe_pipeline(
            temp_file_path,
            chunk_length_s=30,
            batch_size=1,
            generate_kwargs={
                'task': 'transcribe',
                'language': 'english',
            },
        )
        
        # Delete the temporary file
        os.unlink(temp_file_path)
        
        # Return the transcription result
        return JSONResponse(content={"transcript": outputs["text"].strip()})
    
    except Exception as e:
        logger.error(f"Error processing uploaded file: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process file: {str(e)}"},
        )

@app.get("/transcript")
def _(webrtc_id: str):
    logger.debug(f"New transcript stream request for webrtc_id: {webrtc_id}")
    async def output_stream():
        try:
            async for output in stream.output_stream(webrtc_id):
                transcript = output.args[0]
                logger.debug(f"Sending transcript for {webrtc_id}: {transcript[:50]}...")
                yield f"event: output\ndata: {transcript}\n\n"
        except Exception as e:
            logger.error(f"Error in transcript stream for {webrtc_id}: {str(e)}")
            raise

    return StreamingResponse(output_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    port = os.getenv("PORT", 7860)
    
    import uvicorn
    logger.info("Launching FastAPI server")
    uvicorn.run(app, host=SERVER_NAME, port=port)