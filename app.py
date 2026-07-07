import streamlit as st
import requests
import pandas as pd
import math
import re
import urllib.parse
from io import BytesIO

# pypdf-ஐ முயற்சி செய்கிறோம், இல்லை என்றால் pypdf2
try:
    import pypdf
    PDF_READER = "pypdf"
except ImportError:
    try:
        import PyPDF2 as pypdf
        PDF_READER = "pypdf2"
    except ImportError:
        PDF_READER = "none"

st.set_page_config(page_title="Stamford Smart Router", layout="wide")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-size: 16px; font-weight: bold; }
    .driver-card { padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 10px; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚚 Stamford Smart Router")
st.write("PDF-ஐ அப்لوட் செய்து, 10 கிமீ ரேடியஸில் உள்ள மற்ற டிரைவர்கள் மற்றும் ஆன்-கோயிங் பஃபேக்களை உடனே கண்டறியுங்கள்.")

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

uploaded_file = st.file_uploader("📂 உங்கள் தினசரி PDF கோப்பை (Daily Services Schedule) இங்கே அப்லோட் செய்யவும்:", type=["pdf"])

if uploaded_file is not None:
    extracted_jobs = []
    
    try:
        # pypdf மூலம் PDF படிக்கப்படுகிறது
        pdf_file = BytesIO(uploaded_file.read())
        if PDF_READER == "pypdf":
            reader = pypdf.PdfReader(pdf_file)
            num_pages = len(reader.pages)
            for i in range(num_pages):
                text = reader.pages[i].extract_text()
                if text:
                    for line in text.split('\n'):
                        postal_match = re.search(r'\b\d{6}\b', line)
                        if postal_match:
                            postal = postal_match.group(0)
                            order_match = re.search(r'ST\d{4}-\d{5}', line)
                            order_no = order_match.group(0) if order_match else "ST-ORDER"
                            extracted_jobs.append({"Postal": postal, "OrderNo": order_no, "Line": line})
        else:
            st.error("சர்வரில் PDF ரீடர் டூல் இல்லை. தயவுசெய்து ஆப்பை ரீபூட் செய்யவும்.")
    except Exception as e:
        st.error(f"PDF படிப்பதில் சிக்கல்: {e}")

    final_jobs = []
    if extracted_jobs:
        st.success("PDF வெற்றிகரமாகப் படிக்கப்பட்டது!")
        for job in extracted_jobs:
            geo = get_onemap_data(job['Postal'])
            if geo:
                final_jobs.append({
                    "SN": "Log",
                    "OrderNo": job['OrderNo'],
                    "Pax": "Check PDF",
                    "Address": geo['address'],
                    "Time": "Scheduled",
                    "Latitude": geo['lat'],
                    "Longitude": geo['lng']
                })

    if final_jobs:
        df = pd.DataFrame(final_jobs).drop_duplicates(subset=['OrderNo', 'Address'])
        st.subheader("🔍 உங்கள் தற்போதைய லொகேஷனை உள்ளிடவும்")
        search_input = st.text_input("உங்களுடைய அட்ரஸ் அல்லது 6-இலக்க போஸ்டல் கோடு (Current Location):", placeholder="எ.கா: 730768")
        radius_km = st.slider("தேட வேண்டிய தூர ரேடியஸ் (KM):", min_value=1, max_value=20, value=10)
        
        if st.button("SEARCH NEARBY JOBS") and search_input:
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
                map_data = [{"lat": search_geo['lat'], "lon": search_geo['lng']}]
                
                for _, row in df.iterrows():
                    dist = calculate_distance(search_geo['lat'], search_geo['lng'], row['Latitude'], row['Longitude'])
                    if dist <= radius_km:
                        row_dict = row.to_dict()
                        row_dict['Distance'] = round(dist, 2)
                        nearby_list.append(row_dict)
                        map_data.append({"lat": row['Latitude'], "lon": row['Longitude']})
                        
                if len(map_data) > 1:
                    st.subheader("🗺️ அருகில் உள்ள பஃபேக்களின் வரைபடம் (Map View)")
                    st.map(pd.DataFrame(map_data))
                    
                st.subheader(f"📋 வித்தின் {radius_km} KM ரேடியஸிற்குள் இருக்கும் ஆன்-கோயிங் பஃபேக்கள்:")
                if nearby_list:
                    sorted_list = sorted(nearby_list, key=lambda x: x['Distance'])
                    for job in sorted_list:
                        st.markdown(f'''
                        <div class="driver-card">
                            <h4>📦 ஆர்டர்: {job['OrderNo']} ({job['Distance']} KM அருகில்)</h4>
                            <p><b>📍 முகவரி:</b> {job['Address']}</p>
                            <p><b>🕒 விவரம்:</b> {job['Time']}</p>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            gmaps_url = f"http://maps.google.com/?q={job['Latitude']},{job['Longitude']}"
                            st.markdown(f'<a href="{gmaps_url}" target="_blank"><button style="width:100%; background-color:#4CAF50; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">🗺️ GOOGLE MAP ROUTE</button></a>', unsafe_allow_html=True)
                        with col2:
                            msg = f"மச்சான், நான் உன் பக்கத்துல {job['Distance']} KM-ல தான் இருக்கேன். {job['OrderNo']} - {job['Address']} பஃபேக்கு உதவி வேணுமா?"
                            whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
                            st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">💬 WHATSAPP</button></a>', unsafe_allow_html=True)
                        st.write("---")
                else:
                    st.warning("இந்த லொகேஷனைச் சுற்றி வேறு எந்த ஆர்டர்களும் இல்லை.")
            else:
                st.error("முகவரியைக் கண்டறிய முடியவில்லை. தயவுசெய்து சரியான போஸ்டல் கோடை உள்ளிடவும்.")
    else:
        st.warning("PDF-லிருந்து போஸ்டல் கோடுகளைப் பிரித்தெடுக்க முடியவில்லை.")
