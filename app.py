import streamlit as st
import pdfplumber
import requests
import pandas as pd
import math
import re
import urllib.parse
from datetime import datetime

# மொபைல் ஸ்கிரீனிற்கு ஏற்ற வடிவமைப்பு
st.set_page_config(page_title="Stamford Smart Router", layout="wide")

st.markdown("""
    <style>
    .reportview-container .main .block-container{ max-width: 100%; padding-top: 1rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-size: 16px; font-weight: bold; }
    .driver-card { padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 10px; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚚 Stamford Smart Router (Mobile Version)")
st.write("PDF-ஐ அப்லோட் செய்து, 10 கிமீ ரேடியஸில் உள்ள மற்ற டிரைவர்கள் மற்றும் ஆர்டர்களை உடனே கண்டறியுங்கள்.")

# 1. OneMap API மூலம் லொகேஷன் எடுக்கும் ஃபங்க்ஷன்
@st.cache_data(show_spinner=False)
def get_onemap_data(postal_code):
    if not postal_code or len(postal_code) < 6:
        return None
    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
    try:
        response = requests.get(url, timeout=5).json()
        if response['results']:
            result = response['results'][0]
            return {
                "lat": float(result['LATITUDE']),
                "lng": float(result['LONGITUDE']),
                "address": result['ADDRESS']
            }
        return None
    except:
        return None

# 2. தூரத்தைக் கணக்கிடும் ஃபங்க்ஷன் (Haversine Formula)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # ரேடியஸ் கிமீ-ல்
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- PDF அப்லோடு பகுதி ---
uploaded_file = st.file_uploader("📂 உங்கள் தினசரி PDF கோப்பை இங்கே அப்லோட் செய்யவும்:", type=["pdf"])

if uploaded_file is not None:
    st.success("PDF வெற்றிகரமாகப் படிக்கப்பட்டது!")
    
    extracted_jobs = []
    
    # PDF-லிருந்து தகவல்களைப் பிரித்தல் (S/N, Order, Address, Driver, Time)
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                # 6 இலக்க போஸ்டல் கோடுகளைத் தேடுதல்
                postals = re.findall(r'\b\d{6}\b', text)
                for postal in set(postals):
                    geo = get_onemap_data(postal)
                    if geo:
                        # மாதிரி தரவு (உண்மையான PDF கட்டமைப்பிற்கு ஏற்ப இதை இன்னும் துல்லியமாக்கலாம்)
                        # தற்போதைக்கு PDF-ல் உள்ள பொதுவான விவரங்களை மேட்ச் செய்கிறோம்
                        extracted_jobs.append({
                            "Postal": postal,
                            "Address": geo['address'],
                            "Latitude": geo['lat'],
                            "Longitude": geo['lng'],
                            "OrderNo": "ST2607-" + postal[:4], # மாதிரி ஆர்டர் எண்
                            "Driver": "Driver (" + postal[-2:] + ")", # மாதிரி டிரைவர்
                            "Time": "11:00 AM",
                            "Pax": 50
                        })
    
    df = pd.DataFrame(extracted_jobs).drop_duplicates(subset=['Postal'])
    
    # --- மெயின் ரெக்யூர்மென்ட்: மொபைல் சர்ச் பார் ---
    st.subheader("🔍 உங்கள் தற்போதைய லொகேஷனை உள்ளிடவும்")
    search_input = st.text_input("உங்களுடைய அட்ரஸ் அல்லது 6-இலக்க போஸ்டல் கோடு:", placeholder="எ.கா: 730768 (Woodlands)")
    radius_km = st.slider("தேட வேண்டிய தூர ரேடியஸ் (KM):", min_value=1, max_value=20, value=10)
    
    if st.button("SEARCH NEARBY JOBS") and search_input:
        with st.spinner("அருகில் உள்ள இடங்களை கணக்கிடுகிறது..."):
            search_geo = get_onemap_data(search_input) if search_input.isdigit() else None
            
            # அட்ரஸ் பெயராக இருந்தால் OneMap-ல் தேடுதல்
            if not search_geo:
                url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={urllib.parse.quote(search_input)}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
                try:
                    res = requests.get(url).json()
                    if res['results']:
                        search_geo = {"lat": float(res['results'][0]['LATITUDE']), "lng": float(res['results'][0]['LONGITUDE']), "address": res['results'][0]['ADDRESS']}
                except:
                    pass
            
            if search_geo:
                st.info(f"📍 நீங்கள் தேடும் இடம்: **{search_geo['address']}**")
                
                nearby_list = []
                map_data = []
                
                for _, row in df.iterrows():
                    dist = calculate_distance(search_geo['lat'], search_geo['lng'], row['Latitude'], row['Longitude'])
                    if dist <= radius_km:
                        row_dict = row.to_dict()
                        row_dict['Distance'] = round(dist, 2)
                        nearby_list.append(row_dict)
                        # மேப்பிற்கான டேட்டா
                        map_data.append({"lat": row['Latitude'], "lon": row['Longitude']})
                
                # 1. மேப் வியூ (Map Integration)
                if map_data:
                    st.subheader("🗺️ அருகில் உள்ள பஃபேக்களின் வரைபடம் (Map View)")
                    map_df = pd.DataFrame(map_data)
                    # பயனர் இருக்கும் இடத்தையும் மேப்பில் சேர்க்கிறோம்
                    map_df = pd.concat([map_df, pd.DataFrame([{"lat": search_geo['lat'], "lon": search_geo['lng']}])])
                    st.map(map_df)
                
                # 2. பில்டர் செய்யப்பட்ட லிஸ்ட் (Results Display)
                st.subheader(f"📋 {radius_km} KM ரேடியஸிற்குள் உள்ள ஆர்டர்கள் ({len(nearby_list)} கண்டறியப்பட்டது):")
                
                if nearby_list:
                    # தூரத்தின் அடிப்படையில் வரிசைப்படுத்துதல் (Nearest First)
                    sorted_list = sorted(nearby_list, key=lambda x: x['Distance'])
                    
                    for job in sorted_list:
                        # மொபைல் கார்டு வடிவமைப்பு (Driver Cards)
                        st.markdown(f"""
                        <div class="driver-card">
                            <h4>📦 ஆர்டர்: {job['OrderNo']} ({job['Distance']} KM அருகில்)</h4>
                            <p><b>📍 முகவரி:</b> {job['Address']}</p>
                            <p><b>🕒 வருகை நேரம்:</b> {job['Time']} | 👥 <b>Pax:</b> {job['Pax']}</p>
                            <p><b>👤 நியமிக்கப்பட்ட டிரைவர்:</b> {job['Driver']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # இன்டெலிஜென்ட் பட்டன்கள் (கூகுள் மேப் மற்றும் வாட்ஸ்அப்)
                        col1, col2 = st.columns(2)
                        with col1:
                            # கூகுள் மேப் நேவிகேஷன் லிங்க்
                            gmaps_url = f"https://www.google.com/maps/search/?api=1&query={job['Latitude']},{job['Longitude']}"
                            st.markdown(f'href="{gmaps_url}" target="_blank"><button style="width:100%; background-color:#4CAF50; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">🗺️ GOOGLE MAP</button></a>', unsafe_allow_html=True)
                        with col2:
                            # வாட்ஸ்அப் மெசேஜ் லிங்க்
                            msg = f"மச்சான், நான் உன் பக்கத்துல {job['Distance']} KM-ல தான் இருக்கேன். {job['OrderNo']} - {job['Address']} பஃபேக்கு உதவி வேணுமா?"
                            whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
                            st.markdown(f'href="{whatsapp_url}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">💬 WHATSAPP</button></a>', unsafe_allow_html=True)
                        st.write("---")
                else:
                    st.warning("இந்த லொகேஷனைச் சுற்றி 10 கிமீ-க்குள் வேறு எந்த ஆர்டர்களும் இல்லை.")
            else:
                st.error("மன்னிக்கவும், நீங்கள் உள்ளிட்ட முகவரியைக் கண்டறிய முடியவில்லை. தயவுசெய்து சரியான போஸ்டல் கோடை உள்ளிடவும்.")
