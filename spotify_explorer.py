import streamlit as st
import openai
import requests
import json

SPOTIFY_API_DOC = """
La API de Spotify permite buscar y obtener información de artistas, álbumes, canciones, playlists, etc.
Principales endpoints:
- GET /v1/search?q={query}&type={type}: Busca en Spotify (type: track, album, artist, playlist)
- GET /v1/artists/{id}: Info de un artista
- GET /v1/tracks/{id}: Info de una canción
- GET /v1/albums/{id}: Info de un álbum
- GET /v1/playlists/{id}: Info de una playlist
- GET /v1/artists/{id}/top-tracks: Top canciones de un artista
"""

def clean_llm_json(text):
    text = text.strip()
    first_brace = text.find('{')
    if first_brace != -1:
        text = text[first_brace:]
    last_brace = text.rfind('}')
    if last_brace != -1:
        text = text[:last_brace+1]
    text = text.replace("```json", "").replace("```", "").strip()
    return text

class SpotifyAPIExplorer:
    def __init__(self, client_id, client_secret, openai_api_key):
        self.client_id = client_id
        self.client_secret = client_secret
        self.openai_api_key = openai_api_key
        self.access_token = self.get_access_token()

    def get_access_token(self):
        url = 'https://accounts.spotify.com/api/token'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {'grant_type': 'client_credentials'}
        resp = requests.post(url, headers=headers, data=data, auth=(self.client_id, self.client_secret))
        resp.raise_for_status()
        return resp.json()['access_token']

    def run_query(self, user_query):
        openai.api_key = self.openai_api_key
        prompt = (
            f"{SPOTIFY_API_DOC}\n"
            "Eres un agente que recibe consultas de usuario y las traduce a llamadas HTTP a la API de Spotify. "
            "Para cada consulta de usuario, responde en JSON con los campos: 'endpoint', 'method', 'params'. "
            "Ejemplo de output:\n"
            "{'endpoint': '/v1/search', 'method': 'GET', 'params': {'q': 'Beatles', 'type': 'artist'}}\n\n"
            f"Consulta de usuario: '{user_query}'\n"
            "Output:"
        )
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0
        )
        response = completion.choices[0].message.content
        response = clean_llm_json(response.replace("'", '"'))
        try:
            api_call = json.loads(response)
        except json.JSONDecodeError:
            st.error(f"Error interpretando la respuesta del LLM: {response}")
            return None
        url = f"https://api.spotify.com{api_call['endpoint']}"
        headers = {'Authorization': f'Bearer {self.access_token}'}
        params = api_call.get('params', {})
        resp = requests.request(api_call['method'], url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

# --- Interfaz Streamlit Mejorada ---

st.set_page_config(page_title="Spotify API Explorer", page_icon="🎧", layout="centered")
st.markdown(
    """
    <style>
    .stApp {background-color: #181818;}
    .main-card {background: #232323; border-radius: 16px; padding: 18px; color: #eee;}
    .result-title {color: #1DB954; font-weight: bold;}
    a {color: #1DB954;}
    </style>
    """, unsafe_allow_html=True
)
st.markdown('<h1 style="color:#1DB954;text-align:center">Spotify API Explorer 🎧</h1>', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#eee">Haz preguntas sobre artistas, discos, playlists, canciones o consulta cualquier dato de Spotify.</div>',
    unsafe_allow_html=True
)
st.markdown("---")

# --- Configuración de credenciales desde secrets o manual ---

def get_cred_or_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return default

with st.expander("Configura tus credenciales", expanded=True):
    default_client_id = get_cred_or_secret("SPOTIFY_CLIENT_ID")
    default_client_secret = get_cred_or_secret("SPOTIFY_CLIENT_SECRET")
    default_openai_api_key = get_cred_or_secret("OPENAI_API_KEY")

    client_id = st.text_input("Spotify Client ID", value=default_client_id)
    client_secret = st.text_input("Spotify Client Secret", value=default_client_secret, type="password")
    openai_api_key = st.text_input("OpenAI API Key", value=default_openai_api_key, type="password")


user_query = st.text_input("Pregunta sobre Spotify", "")

if st.button("Buscar") and client_id and client_secret and openai_api_key and user_query:
    explorer = SpotifyAPIExplorer(client_id, client_secret, openai_api_key)
    with st.spinner("Consultando..."):
        try:
            result = explorer.run_query(user_query)
            if not result:
                st.error("No se obtuvo resultado de la API.")
            elif "error" in result and result["error"]:
                st.warning(result.get("msg", "Ha ocurrido un error inesperado con la API de Spotify."))
            elif "artists" in result:
                st.markdown('<div class="main-card"><span class="result-title">Artistas encontrados:</span><br>' +
                    "<br>".join([f"🎤 <a href='{a['external_urls']['spotify']}' target='_blank'>{a['name']}</a>" for a in result["artists"]["items"]]) +
                    "</div>", unsafe_allow_html=True)
            elif "albums" in result:
                st.markdown('<div class="main-card"><span class="result-title">Álbumes encontrados:</span><br>' +
                    "<br>".join([f"💿 <a href='{a['external_urls']['spotify']}' target='_blank'>{a['name']}</a> ({a['release_date']})" for a in result["albums"]["items"]]) +
                    "</div>", unsafe_allow_html=True)
            elif "tracks" in result:
                st.markdown('<div class="main-card"><span class="result-title">Canciones encontradas:</span><br>' +
                    "<br>".join([f"🎵 <a href='{t['external_urls']['spotify']}' target='_blank'>{t['name']}</a> - {', '.join([ar['name'] for ar in t['artists']])}" for t in result["tracks"]["items"]]) +
                    "</div>", unsafe_allow_html=True)
            elif "playlists" in result:
                st.markdown('<div class="main-card"><span class="result-title">Playlists encontradas:</span><br>' +
                    "<br>".join([f"📜 <a href='{p['external_urls']['spotify']}' target='_blank'>{p['name']}</a> ({p['description']})" for p in result["playlists"]["items"]]) +
                    "</div>", unsafe_allow_html=True)
            elif "audio_analysis" in result or "audio_features" in result:
                st.warning("🚫 La API pública de Spotify ya no permite acceder al análisis avanzado de canciones (loudness, valence, danceability, etc). Solo puedo mostrar información básica sobre canciones, discos, artistas y playlists.")
            else:
                st.json(result)
        except Exception as e:
            st.error(f"Error: {e}")




