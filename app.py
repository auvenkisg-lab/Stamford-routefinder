import streamlit as st
import pdfplumber
import requests
import pandas as pd
import math
import re
import urllib.parse

st.set_page_config(page_title="Stamford Smart Router", layout="wide")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-size: 16px; font-weight: bold; }
    .driver-card { padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 10px; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚚 Stamford Smart Router (Bulit-proof Ver)")
st.write("PDF-ஐ அப்لوட் செய்து, குறிப்பிட்ட ரேடியஸில் உள்ள மற்ற டிரைவர்கள் மற்றும் பஃபேக்களை உடனே கண்டறியுங்கள்.")

@st.cache_data(show_spinner=False)
def get_onemap_data(postal_code):
    if not postal_code or len(postal_code) < 6:
        return None
    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
    try:
        response = requests.get(url, timeout=5).json()
        if response['results']:
            result = response['results'][0]
            return {"lat": float(result['LATITUDE']), "lng": float(result['LONGITUDE']), "address": result['ADDRESS']}
        return None
    except:
        return None

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - math.radians(lat1)) # Correcting variable name issue just in case
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

uploaded_file = st.file_uploader("📂 உங்கள் தினசரி PDF கோப்பை (Daily Services Schedule) இங்கே அப்لوட் செய்யவும்:", type=["pdf"])

if uploaded_file is not None:
    extracted_jobs = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
                
            # வரிகளாகப் பிரிக்கிறது
            lines = text.split('\n')
            for line in lines:
                # 6 இலக்க எண்ணை மட்டும் தேடுகிறது (முன்னாடி பின்னாடி எழுத்துக்கள் இருந்தாலும் கண்டுபிடிக்கும்)
                postal_match = re.search(r'(?<!\d)\d{6}(?!\d)', line)
                if postal_match:
                    postal = postal_match.group(0)
                    
                    # Stamford / Select Catering ஆர்டர் நம்பரைத் தேடுகிறது (ST... அல்லது SC...)
                    order_match = re.search(r'\b(ST|SC)\d{4,8}[-\d]*\b', line, re.IGNORECASE)
                    order_no = order_match.group(0) if order_match else f"JOB-{postal}"
                    
                    # வரிகளின் ஆரம்பத்தில் இருக்கும் S/N நம்பரை எடுக்கிறது
                    sn_match = re.match(r'^\s*"?(\d+)\b', line)
                    sn = sn_match.group(1) if sn_match else "-"
                    
                    # தேவையில்லாத கம்பெனி போஸ்டல் கோடை (758099) தவிர்க்கிறது
                    if postal == "758099":
                        continue
                        
                    # கிளீன் செய்யப்பட்ட வரி விவரம்
                    clean_line = line.replace('"', '').replace(',', ' ').strip()
                    
                    extracted_jobs.append({
                        "SN": sn,
                        "OrderNo": order_no.upper(),
                        "Address": clean_line,
                        "Postal": postal
                    })
                    
    if extracted_jobs:
        df = pd.DataFrame(extracted_jobs).drop_duplicates(subset=['OrderNo', 'Postal'])
        st.success(f"🎉 PDF சல்லடை போட்டு படிக்கப்பட்டது! மொத்தம் {len(df)} பஃபே ஆர்டர்கள் வெற்றிகரமாகக் கண்டறியப்பட்டன.")
        
        st.subheader("🔍 உங்கள் தற்போதைய லொகேஷனை உள்ளிடவும்")
        search_input = st.text_input("உங்களுடைய அட்ரஸ் அல்லது 6-இலக்க போஸ்டல் கோடு (Current Location):", placeholder="எ.கா: 730768")
        radius_km = st.slider("தேட வேண்டிய தூர ரேடியஸ் (KM):", min_value=1, max_value=20, value=10)
        
        if st.button("SEARCH NEARBY JOBS") and search_input:
            with st.spinner("லொகேஷன் தேடப்படுகிறது..."):
                search_geo = get_onemap_data(search_input) if search_input.isdigit() else None
                if not search_geo:
                    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={urllib.parse.quote(search_input)}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
                    try:
                        res = requests.get(url).json()
                        if res['results']:
                            search_geo = {"lat": float(res['results'][0]['LATITUDE']), "lng": float(res['results'][0]['LONGITUDE']), "address": res['results'][0]['ADDRESS']}
                    except: pass
                    
                if search_geo:
                    st.info(f"📍 நீங்கள் தேடும் இடம்: **{search_geo['address']}**")
                    nearby_list = []
                    map_data = [{"lat": search_geo['lat'], "lon": search_geo['lng'], "type": "Current"}]
                    
                    for _, row in df.iterrows():
                        job_geo = get_onemap_data(row['Postal'])
                        if job_geo:
                            dist = calculate_distance(search_geo['lat'], search_geo['lng'], job_geo['lat'], job_geo['lng'])
                            if dist <= radius_km:
                                row_dict = row.to_dict()
                                row_dict['Distance'] = round(dist, 2)
                                row_dict['Lat'] = job_geo['lat']
                                row_dict['Lng'] = job_geo['lng']
                                nearby_list.append(row_dict)
                                map_data.append({"lat": job_geo['lat'], "lon": job_geo['lng'], "type": "Job"})
                            
                    if len(map_data) > 1:
                        st.subheader("🗺️ அருகில் உள்ள பஃபேக்களின் வரைபடம் (Map View)")
                        st.map(pd.DataFrame(map_data)[['lat', 'lon']])
                        
                    st.subheader(f"📋 வித்தின் {radius_km} KM ரேடியஸிற்குள் இருக்கும் பஃபேக்கள்:")
                    if nearby_list:
                        sorted_list = sorted(nearby_list, key=lambda x: x['Distance'])
                        for job in sorted_list:
                            st.markdown(f'''
                            <div class="driver-card">
                                <h4>📦 S/N: {job['SN']} | ஆர்டர்: {job['OrderNo']} ({job['Distance']} KM அருகில்)</h4>
                                <p><b>📍 முழு விவரம்:</b> {job['Address']}</p>
                            </div>
                            ''', unsafe_allow_html=True)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                gmaps_url = f"https://www.google.com/maps/search/?api=1&query={job['Lat']},{job['Lng']}"
                                st.markdown(f'<a href="{gmaps_url}" target="_blank"><button style="width:100%; background-color:#4CAF50; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">🗺️ GOOGLE MAP ROUTE</button></a>', unsafe_allow_html=True)
                            with col2:
                                msg = f"மச்சான், நான் உன் பக்கத்துல {job['Distance']} KM-ல தான் இருக்கேன். S/N: {job['SN']} | {job['OrderNo']} பஃபேக்கு உதவி வேணுமா?"
                                whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
                                st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">💬 WHATSAPP</button></a>', unsafe_allow_html=True)
                            st.write("---")
                    else:
                        st.warning(f"இந்த லொகேஷனைச் சுற்றி {radius_km} கிமீ-க்குள் வேறு எந்த ஆர்டர்களும் இல்லை.")
                else:
                    st.error("முகவரியைக் கண்டறிய முடியவில்லை. தயவுசெய்து சரியான போஸ்டல் கோடை உள்ளிடவும்.")
    else:
        st.warning("PDF-லிருந்து போஸ்டல் கோடுகளைப் பிரித்தெடுக்க முடியவில்லை. ஃபைல் ஃபார்மட்டைச் சரிபார்க்கவும்.")
