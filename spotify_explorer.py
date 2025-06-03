import streamlit as st
import openai
import requests
import json
import matplotlib.pyplot as plt

# --- Documentación corta para el LLM ---
SPOTIFY_API_DOC = """
La API de Spotify permite buscar y obtener información de artistas, álbumes, canciones, playlists, etc.
Principales endpoints:
- GET /v1/search?q={query}&type={type}: Busca en Spotify (type: track, album, artist, playlist)
- GET /v1/artists/{id}: Info de un artista
- GET /v1/tracks/{id}: Info de una canción
- GET /v1/albums/{id}: Info de un álbum
- GET /v1/playlists/{id}: Info de una playlist
- GET /v1/playlists/{id}/tracks: Tracks de una playlist
- GET /v1/artists/{id}/top-tracks: Top canciones de un artista
- GET /v1/audio-features/{id}: Características de audio de una canción
- GET /v1/audio-analysis/{id}: Análisis de audio avanzado de una canción
- GET /v1/recommendations: Recomendaciones musicales (seed_tracks, seed_artists)
"""

AUDIO_FEATURES_DESCRIPTIONS = {
    "acousticness": "Probabilidad de que la canción sea acústica (1 = acústica, 0 = no).",
    "danceability": "Describe lo adecuada que es una canción para bailar (0-1).",
    "energy": "Medida de intensidad y actividad (0-1).",
    "instrumentalness": "Probabilidad de que la pista no contenga voces (1 = instrumental).",
    "liveness": "Probabilidad de que la grabación sea en vivo (0-1).",
    "loudness": "Volumen promedio de la pista en decibelios.",
    "speechiness": "Detecta la presencia de palabras habladas.",
    "valence": "Positividad/alegría de la canción (0 = triste, 1 = alegre).",
    "tempo": "Velocidad estimada de la canción (BPM).",
    "key": "Clave musical (0 = C, 1 = C♯/D♭, ..., 11 = B)",
    "mode": "Modalidad: 1 = mayor, 0 = menor.",
    "duration_ms": "Duración de la pista en milisegundos."
}

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

def extract_spotify_items(result):
    for key in ['albums', 'artists', 'tracks', 'playlists']:
        if key in result:
            items = result[key].get('items', [])
            out = []
            for i in items:
                data = {}
                if key == "albums":
                    data = {
                        "title": i.get("name"),
                        "type": i.get("album_type"),
                        "artist": ", ".join(a["name"] for a in i.get("artists", [])),
                        "release": i.get("release_date", ""),
                        "image": i.get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", ""),
                        "id": i.get("id"),
                        "spotify_type": "album"
                    }
                elif key == "tracks":
                    data = {
                        "title": i.get("name"),
                        "artist": ", ".join(a["name"] for a in i.get("artists", [])),
                        "album": i.get("album", {}).get("name", ""),
                        "image": i.get("album", {}).get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", ""),
                        "id": i.get("id"),
                        "spotify_type": "track"
                    }
                elif key == "artists":
                    data = {
                        "title": i.get("name"),
                        "type": i.get("type"),
                        "image": i.get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", ""),
                        "id": i.get("id"),
                        "spotify_type": "artist"
                    }
                elif key == "playlists":
                    data = {
                        "title": i.get("name"),
                        "type": "playlist",
                        "image": i.get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", ""),
                        "description": i.get("description", ""),
                        "id": i.get("id"),
                        "spotify_type": "playlist"
                    }
                out.append(data)
            return out
    return None

def get_audio_features(track_id, access_token):
    url = f"https://api.spotify.com/v1/audio-features/{track_id}"
    headers = {'Authorization': f'Bearer {access_token}'}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def get_audio_analysis(track_id, access_token):
    url = f"https://api.spotify.com/v1/audio-analysis/{track_id}"
    headers = {'Authorization': f'Bearer {access_token}'}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def plot_audio_features(features):
    feature_keys = [
        "acousticness", "danceability", "energy", "instrumentalness",
        "liveness", "speechiness", "valence"
    ]
    values = [features[k] for k in feature_keys]
    labels = [k.capitalize() for k in feature_keys]

    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.barh(labels, values, color="#1DB954")
    ax.set_xlim(0, 1)
    ax.set_title("Spotify Audio Features")
    ax.set_xlabel("Valor (0-1)")
    for i, bar in enumerate(bars):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2, f"{values[i]:.2f}", va="center")
    plt.tight_layout()
    return fig

def get_recommendations(seed_tracks=None, seed_artists=None, access_token=None):
    url = "https://api.spotify.com/v1/recommendations"
    params = {}
    if seed_tracks:
        params["seed_tracks"] = seed_tracks
    if seed_artists:
        params["seed_artists"] = seed_artists
    headers = {'Authorization': f'Bearer {access_token}'}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json().get("tracks", [])

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

    def llm_call(self, user_query):
        openai.api_key = self.openai_api_key
        prompt = (
            f"{SPOTIFY_API_DOC}\n"
            "Eres un agente que recibe consultas de usuario y las traduce a llamadas HTTP a la API de Spotify. "
            "Devuelve solo la última llamada necesaria para responder la consulta. "
            "Si la llamada requiere un ID, devuelve la llamada usando el endpoint y los parámetros con '{id}'. "
            "No des explicaciones. Ejemplo:\n"
            "{\"endpoint\": \"/v1/search\", \"method\": \"GET\", \"params\": {\"q\": \"Beatles\", \"type\": \"artist\"}}\n"
            f"Consulta de usuario: '{user_query}'\n"
            "Output:"
        )
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0
        )
        return completion.choices[0].message.content

    def pipeline_query(self, user_query):
        # 1. Llama al LLM y parsea la respuesta
        response = self.llm_call(user_query)
        try:
            api_call = json.loads(clean_llm_json(response.replace("'", '"')))
        except Exception:
            st.error(f"Error interpretando la respuesta del LLM: {response}")
            return None

        # 2. ¿Es una llamada con {id} o "track_id"? Si sí, lanza la búsqueda y la segunda llamada
        if (
            (api_call['endpoint'].endswith('/{id}') or api_call['endpoint'].endswith('/track_id'))
            or any(str(v).lower() in ['{id}', 'track_id'] for v in api_call.get("params", {}).values())
        ):
            # Extrae el nombre de la canción o artista del user_query usando comillas o split
            import re
            quoted = re.findall(r'"([^"]+)"', user_query)
            if quoted:
                search_query = quoted[0]
            else:
                search_query = user_query
            search_params = {
                "endpoint": "/v1/search",
                "method": "GET",
                "params": {"q": search_query, "type": "track"}
            }
            url = f"https://api.spotify.com{search_params['endpoint']}"
            headers = {'Authorization': f'Bearer {self.access_token}'}
            resp = requests.request(
                search_params['method'], url, headers=headers, params=search_params['params']
            )
            resp.raise_for_status()
            tracks = resp.json().get('tracks', {}).get('items', [])
            if not tracks:
                st.error("No se encontró la canción.")
                return None
            track_id = tracks[0]['id']

            # Llama al endpoint final con el id encontrado
            endpoint_final = api_call['endpoint'].replace('{id}', track_id).replace('track_id', track_id)
            url_final = f"https://api.spotify.com{endpoint_final}"
            # Quita params 'id'/'track_id' si ya está en el endpoint
            new_params = {
                k: v for k, v in api_call.get('params', {}).items()
                if str(v).lower() not in ['{id}', 'track_id'] and k not in ['id', 'track_id']
            }
            resp2 = requests.request(
                api_call['method'],
                url_final,
                headers=headers,
                params=new_params
            )

            resp2.raise_for_status()
            return resp2.json()
        else:
            # Llama normal
            url = f"https://api.spotify.com{api_call['endpoint']}"
            headers = {'Authorization': f'Bearer {self.access_token}'}
            resp = requests.request(api_call['method'], url, headers=headers, params=api_call.get('params', {}))
            resp.raise_for_status()
            return resp.json()

# --- Interfaz Streamlit ---

st.title("Spotify API Explorer con LLM + Features + Pipeline")
client_id = st.text_input("Spotify Client ID")
client_secret = st.text_input("Spotify Client Secret", type="password")
openai_api_key = st.text_input("OpenAI API Key", type="password")
user_query = st.text_input("Pregunta sobre Spotify", "")

if st.button("Buscar") and client_id and client_secret and openai_api_key and user_query:
    explorer = SpotifyAPIExplorer(client_id, client_secret, openai_api_key)
    with st.spinner("Consultando..."):
        try:
            result = explorer.pipeline_query(user_query)
            if not result:
                st.warning("Sin resultados.")
            # Para queries de features/análisis:
            elif "loudness" in result or "danceability" in result or "acousticness" in result:
                st.subheader("Audio Features")
                features = result
                fig = plot_audio_features(features)
                st.pyplot(fig)
                st.markdown("**Valores destacados:**")
                for k in AUDIO_FEATURES_DESCRIPTIONS:
                    if k in features:
                        st.markdown(f"- **{k.capitalize()}**: {features[k]} ({AUDIO_FEATURES_DESCRIPTIONS[k]})")
            elif "track" in result or "meta" in result:
                st.json(result)
            else:
                # Para queries normales (álbumes, artistas, playlists, etc)
                out = extract_spotify_items(result)
                if out:
                    st.write(f"Resultados encontrados: {len(out)}")
                    for idx, item in enumerate(out):
                        st.markdown(
                            f"""**{item.get('title', '')}**  
{item.get('artist', '') if 'artist' in item else ''}  
{item.get('release', '') if 'release' in item else ''}  
[Ver en Spotify]({item.get('url', '')})""")
                        if item.get('image'):
                            st.image(item['image'], width=150)
                        st.markdown("---")
                else:
                    st.json(result)
        except Exception as e:
            st.error(f"Error: {e}")





