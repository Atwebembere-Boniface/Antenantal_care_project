import os
import json
import base64
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from google.cloud import dialogflow_v2 as dialogflow
from google.cloud import texttospeech

# Set the path to your Google JSON key
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(__file__), 'credentials/google_key.json')

@csrf_exempt # Use @login_required in production for security
def chat_with_voice(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user_text = data.get("message", "")
        
        project_id = "spry-kingdom-492709-k7" # Replace with your GCP Project ID
        session_id = str(request.user.id) if request.user.is_authenticated else "anonymous"
        
        try:
            # 1. Dialogflow Intent Detection
            session_client = dialogflow.SessionsClient()
            session = session_client.session_path(project_id, session_id)
            text_input = dialogflow.TextInput(text=user_text, language_code="en-US")
            query_input = dialogflow.QueryInput(text=text_input)
            
            response = session_client.detect_intent(request={"session": session, "query_input": query_input})
            bot_text = response.query_result.fulfillment_text

            # 2. Text-to-Speech (The Bot's Voice)
            tts_client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=bot_text)
            
            # Configuring the voice (Neural2 sounds more natural)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US", 
                name="en-US-Neural2-F", # Female Neural voice
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

            tts_response = tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            # Convert audio bytes to Base64 string for the browser
            audio_base64 = base64.b64encode(tts_response.audio_content).decode('utf-8')

            return JsonResponse({
                "bot_text": bot_text,
                "audio_base64": audio_base64
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)