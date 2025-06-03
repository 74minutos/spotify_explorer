import streamlit as st
import requests
import openai
import os

# Configuración
SPOTIFY_CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"] if "SPOTIFY_CLIENT_ID" in st.secrets else os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"] if "SPOTIFY_CLIENT_SECRET" in st.secrets else os.environ.get("SPOTIFY_CLIENT_SECRET")
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"] if "OPENAI_API_KEY" in st.secrets else os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# --- Función para obtener el access token de Spotify ---
def get_spotify_token():
    auth_url = 'https://accounts.spotify.com/api/token'
    auth_resp = requests.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    })
    auth_resp.raise_for_status()
    return auth_resp.json()['access_token']

# --- Función para consultar la API de Spotify ---
def spotify_api_call(endpoint, method="GET", params=None):
    token = get_spotify_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://api.spotify.com/v1" + endpoint

    # No usar endpoints de audio analysis/features
    if any(forbidden in endpoint for forbidden in ["/audio-analysis", "/audio-features"]):
        return {
            "error": True,
            "msg": (
                "🚫 Lo siento, la API pública de Spotify ya no permite acceder al análisis avanzado de canciones "
                "(como loudness, valence, danceability, etc.) por restricciones recientes. "
                "Solo puedo ofrecerte información básica sobre canciones, discos, artistas y playlists."
            ),
        }

    resp = requests.request(method, url, headers=headers, params=params)
    if resp.status_code == 403:
        return {
            "error": True,
            "msg": (
                "🚫 No tienes acceso a este recurso de Spotify (puede estar restringido o no disponible en la API pública)."
            ),
        }
    try:
        return resp.json()
    except Exception:
        return {"error": True, "msg": "Error procesando la respuesta de Spotify."}

# --- Función MCP con GPT-4o ---
def generate_spotify_api_instructions(query):
    prompt = (
        "Eres un agente que traduce consultas humanas a llamadas de la API pública de Spotify Web (solo endpoints públicos: "
        "search, artists, albums, tracks, playlists, recommendations). "
        "Nunca uses audio-analysis ni audio-features, solo dilo si lo piden. "
        "Devuelve SIEMPRE la respuesta en formato JSON así:\n"
        '{ "endpoint": "/v1/...", "method": "GET", "params": {...} }\n'
        "Consulta del usuario: " + query
    )
    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0
    )
    # Extrae JSON de la respuesta del modelo
    import re, json
    response = completion.choices[0].message.content
    match = re.search(r"\{[\s\S]+\}", response)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            return None
    return None

# --- Interfaz Streamlit ---
st.set_page_config(page_title="Agente Spotify", page_icon="🎶", layout="centered")
st.markdown(
    """
    <style>
    .stApp {background-color: #181818;}
    .big-title {font-size:2.2rem; color:#1DB954; text-align:center; font-weight: bold;}
    .subtitle {color: #fff; font-size:1.1rem;}
    .spotify-box {background: #232323; border-radius: 16px; padding: 18px; color: #eee;}
    .result-title {color: #1DB954; font-weight: bold;}
    </style>
    """, unsafe_allow_html=True
)
st.markdown('<div class="big-title">Agente Conversacional Spotify 🎧</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Haz preguntas sobre artistas, discos, playlists, canciones, recomendaciones…</div>', unsafe_allow_html=True)

user_query = st.text_input("Escribe tu consulta sobre Spotify (ej: 'dame discos de Pink Floyd', 'playlist de los 80', 'recomiéndame canciones de rock', etc.):", "")

if user_query:
    api_call = generate_spotify_api_instructions(user_query)
    if not api_call:
        st.error("No pude interpretar tu consulta. Prueba con otra formulación.")
    elif "endpoint" in api_call and any(forbidden in api_call["endpoint"] for forbidden in ["/audio-analysis", "/audio-features"]):
        st.warning(
            "🚫 La API pública de Spotify ya no permite análisis avanzados de canciones. Pide otra cosa (busca artistas, discos, playlists, etc.)"
        )
    else:
        result = spotify_api_call(
            api_call["endpoint"],
            method=api_call.get("method", "GET"),
            params=api_call.get("params", {})
        )
        if "error" in result and result["error"]:
            st.warning(result.get("msg", "Ha ocurrido un error inesperado con la API de Spotify."))
        elif "artists" in result:
            st.markdown(f"<div class='spotify-box'><span class='result-title'>Artistas:</span><br>"
                        + "<br>".join([f"🎤 <a href='{a['external_urls']['spotify']}' target='_blank'>{a['name']}</a>" for a in result["artists"]["items"]])
                        + "</div>", unsafe_allow_html=True)
        elif "albums" in result:
            st.markdown(f"<div class='spotify-box'><span class='result-title'>Álbumes:</span><br>"
                        + "<br>".join([f"💿 <a href='{a['external_urls']['spotify']}' target='_blank'>{a['name']}</a> ({a['release_date']})" for a in result["albums"]["items"]])
                        + "</div>", unsafe_allow_html=True)
        elif "tracks" in result:
            st.markdown(f"<div class='spotify-box'><span class='result-title'>Canciones:</span><br>"
                        + "<br>".join([f"🎵 <a href='{t['external_urls']['spotify']}' target='_blank'>{t['name']}</a> - {', '.join([ar['name'] for ar in t['artists']])}" for t in result["tracks"]["items"]])
                        + "</div>", unsafe_allow_html=True)
        elif "playlists" in result:
            st.markdown(f"<div class='spotify-box'><span class='result-title'>Playlists:</span><br>"
                        + "<br>".join([f"📜 <a href='{p['external_urls']['spotify']}' target='_blank'>{p['name']}</a> ({p['description']})" for p in result["playlists"]["items"]])
                        + "</div>", unsafe_allow_html=True)
        elif "error" in result:
            st.warning(result["msg"])
        else:
            # Resultado bruto (para endpoints que no has formateado)
            st.json(result)






