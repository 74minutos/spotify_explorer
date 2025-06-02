# Spotify API Explorer con LLM + Streamlit

Explora la API de Spotify usando lenguaje natural. Pregunta lo que quieras sobre artistas, canciones, álbumes o playlists, y el agente interpreta la consulta, consulta la API de Spotify y te muestra el resultado.

---

## ¿Qué hace este proyecto?

- Te permite preguntar en lenguaje natural:  
  *Ejemplo:* “Busca la canción Blinding Lights”, “Dame información sobre Bad Bunny”, “Lista álbumes de Rosalía”, etc.
- Usa un modelo de OpenAI para traducir tu consulta a una llamada a la API de Spotify.
- Ejecuta la llamada real y muestra el resultado (JSON).

---

## Requisitos

- Python 3.8+
- Una cuenta de [Spotify for Developers](https://developer.spotify.com/dashboard)  
  (necesitas tu `Client ID` y `Client Secret`)
- Una clave de API de [OpenAI](https://platform.openai.com/account/api-keys)
- (Opcional) Cuenta gratuita en [Streamlit Cloud](https://streamlit.io/cloud) si quieres desplegarlo online

---

## Instalación

```bash
git clone https://github.com/TU_USUARIO/spotify-api-explorer.git
cd spotify-api-explorer
pip install -r requirements.txt
