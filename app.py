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

st.title("🚚 Stamford Smart Router")
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
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

uploaded_file = st.file_uploader("📂 உங்கள் தினசரி PDF கோப்பை (Daily Services Schedule) இங்கே அப்لوட் செய்யவும்:", type=["pdf"])

if uploaded_file is not None:
    extracted_jobs = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Stamford PDF-ல் குறைந்தது 5 அல்லது அதற்கு மேற்பட்ட காலம்கள் இருக்கும்
                    if len(row) >= 5:
                        sn = str(row[0]).strip() if row[0] else ""
                        order_no = str(row[1]).strip() if row[1] else ""
                        pax = str(row[2]).strip() if row[2] else ""
                        address = str(row[3]).strip() if row[3] else ""
                        time_info = str(row[4]).strip() if row[4] else ""
                        
                        # அட்ரஸ் காலமில் 6 இலக்க சிங்கப்பூர் போஸ்டல் கோடைத் தேடுகிறது
                        postal_match = re.search(r'\b\d{6}\b', address)
                        if postal_match:
                            postal = postal_match.group(0)
                            
                            # தேவையற்ற ஹெடர்களைத் தவிர்க்கிறது
                            if sn.lower() != "s/n" and order_no != "":
                                extracted_jobs.append({
                                    "SN": sn,
                                    "OrderNo": order_no,
                                    "Pax": pax,
                                    "Address": address.replace('\n', ' '),
                                    "Time": time_info.replace('\n', ' '),
                                    "Postal": postal
                                })
                                    
    if extracted_jobs:
        df = pd.DataFrame(extracted_jobs).drop_duplicates(subset=['OrderNo', 'Postal'])
        st.success(f"PDF வெற்றிகரமாகப் படிக்கப்பட்டது! மொத்தம் {len(df)} ஆர்டர்கள் கண்டறியப்பட்டன.")
        
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
                        
                    st.subheader(f"📋 வித்தின் {radius_km} KM ரேடியஸிற்குள் இருக்கும் ஆன்-கோயிங் பஃபேக்கள்:")
                    if nearby_list:
                        sorted_list = sorted(nearby_list, key=lambda x: x['Distance'])
                        for job in sorted_list:
                            st.markdown(f'''
                            <div class="driver-card">
                                <h4>📦 S/N: {job['SN']} | ஆர்டர்: {job['OrderNo']} ({job['Distance']} KM அருகில்)</h4>
                                <p><b>📍 முகவரி:</b> {job['Address']}</p>
                                <p><b>🕒 வருகை/கலெக்ஷன் நேரம்:</b> {job['Time']} | 👥 <b>Pax:</b> {job['Pax']}</p>
                            </div>
                            ''', unsafe_allow_html=True)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                gmaps_url = f"https://www.google.com/maps/search/?api=1&query={job['Lat']},{job['Lng']}"
                                st.markdown(f'<a href="{gmaps_url}" target="_blank"><button style="width:100%; background-color:#4CAF50; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">🗺️ GOOGLE MAP ROUTE</button></a>', unsafe_allow_html=True)
                            with col2:
                                msg = f"மச்சான், நான் உன் பக்கத்துல {job['Distance']} KM-ல தான் இருக்கேன். S/N: {job['SN']} | {job['OrderNo']} - {job['Address']} பஃபேக்கு உதவி வேணுமா?"
                                whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
                                st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">💬 WHATSAPP</button></a>', unsafe_allow_html=True)
                            st.write("---")
                    else:
                        st.warning(f"இந்த லொகேஷனைச் சுற்றி {radius_km} கிமீ-க்குள் வேறு எந்த ஆர்டர்களும் இல்லை.")
                else:
                    st.error("முகவரியைக் கண்டறிய முடியவில்லை. தயவுசெய்து சரியான போஸ்டல் கோடை உள்ளிடவும்.")
    else:
        st.warning("PDF-லிருந்து போஸ்டல் கோடுகளைப் பிரித்தெடுக்க முடியவில்லை. டேபிள் ஃபார்மட்டைச் சரிபார்க்கவும்.")
