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
- GET /v1/playlists/{id}/tracks: Tracks de una playlist
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

def extract_spotify_items(result):
    # Busca el primer nivel tipo 'albums', 'artists', 'tracks', 'playlists'
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
                        "url": i.get("external_urls", {}).get("spotify", "")
                    }
                elif key == "tracks":
                    data = {
                        "title": i.get("name"),
                        "artist": ", ".join(a["name"] for a in i.get("artists", [])),
                        "album": i.get("album", {}).get("name", ""),
                        "image": i.get("album", {}).get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", "")
                    }
                elif key == "artists":
                    data = {
                        "title": i.get("name"),
                        "type": i.get("type"),
                        "image": i.get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", "")
                    }
                elif key == "playlists":
                    data = {
                        "title": i.get("name"),
                        "type": "playlist",
                        "image": i.get("images", [{}])[0].get("url", ""),
                        "url": i.get("external_urls", {}).get("spotify", ""),
                        "description": i.get("description", "")
                    }
                out.append(data)
            return out
    return None

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

# --- Interfaz Streamlit ---

st.title("Spotify API Explorer (con LLM)")
client_id = st.text_input("Spotify Client ID")
client_secret = st.text_input("Spotify Client Secret", type="password")
openai_api_key = st.text_input("OpenAI API Key", type="password")
user_query = st.text_input("Pregunta sobre Spotify", "")

if st.button("Buscar") and client_id and client_secret and openai_api_key and user_query:
    explorer = SpotifyAPIExplorer(client_id, client_secret, openai_api_key)
    with st.spinner("Consultando..."):
        try:
            result = explorer.run_query(user_query)
            if result:
                out = extract_spotify_items(result)
                if out:
                    st.write(f"Resultados encontrados: {len(out)}")
                    for item in out:
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




