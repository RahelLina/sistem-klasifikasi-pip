import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import io
import hashlib
import base64  
from datetime import datetime
import os
import joblib
import time

from auth import login_admin, reset_password_ui
from database import conn
from classification import predict, MAPPING, REVERSE_MAPPING
# =====================================================
# PAGE CONFIG 
# =====================================================
st.set_page_config(
    page_title="SISTEM KLASIFIKASI PIP",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# =====================================================
# FUNGSI HELPER & CSS
# =====================================================

def local_css(file_name):
    """Membaca file CSS dari folder root atau assets"""
    paths = [file_name, os.path.join("assets", file_name)]
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
            break

def get_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f: 
            return base64.b64encode(f.read()).decode()
    return ""

def classify_and_insert_row(row, cursor):
    """
    Memetakan 1 baris dari Excel (format Klasifikasi_PIP.xlsx) ke database,
    menjalankan prediksi RF, lalu INSERT.
    """
    try:
        # --- 1. Ambil NIPD & Nama ---
        nipd_raw = row.get('NIPD') or row.get('nipd') or 0
        nama_val = str(row.get('Nama') or row.get('nama') or '').strip()
        
        if not nipd_raw or not nama_val or nama_val == 'nan':
            return False
        
        nipd_val = str(int(float(nipd_raw)))

        # --- 2. Cek duplikat ---
        existing = cursor.execute("SELECT id FROM siswa WHERE nipd=?", (nipd_val,)).fetchone()
        if existing:
            return False

        # --- 3. Ambil nilai mentah dari Excel ---
        # Kolom pekerjaan/penghasilan ada di Unnamed karena Excel pakai merged header
        p_ayah_raw = str(row.get('Pekerjaan_Ayah') or row.get('Unnamed: 16') or 'Tidak Bekerja').strip()
        g_ayah_raw = str(row.get('Penghasilan_Ayah') or row.get('Unnamed: 17') or 'Tidak Berpenghasilan').strip()
        p_ibu_raw  = str(row.get('Pekerjaan_Ibu') or row.get('Unnamed: 21') or 'Tidak Bekerja').strip()
        g_ibu_raw  = str(row.get('Penghasilan_Ibu') or row.get('Unnamed: 22') or 'Tidak Berpenghasilan').strip()
        tang_raw   = str(row.get('Jumlah_Tanggungan') or row.get('Jumlah Tanggungan') or '1').strip()
        # Hapus ".0" jika tanggungan berupa float
        if tang_raw.endswith('.0'):
            tang_raw = tang_raw[:-2]

        # Kolom lingkungan — coba nama dengan spasi dan underscore
        def get_col(r, *keys):
            for k in keys:
                v = r.get(k)
                if v is not None and str(v).strip() not in ['', 'nan', 'None']:
                    return str(v).strip()
            return None

        jenis_tinggal   = get_col(row, 'Jenis_Tinggal', 'Jenis Tinggal')
        kepemilikan     = get_col(row, 'Kepemilikan_Rumah', 'Kepemilikan Rumah')
        alat_trans      = get_col(row, 'Alat_Transportasi', 'Alat Transportasi')
        kondisi_kel     = get_col(row, 'Kondisi_Keluarga', 'Kondisi Keluarga')
        penerima_kip    = get_col(row, 'Penerima_KIP', 'Penerima KIP')
        penerima_kps    = get_col(row, 'Penerima_KPS', 'Penerima KPS')

        # --- 4. Normalisasi nilai Excel → format yang dikenali MAPPING ---

        def norm_pekerjaan(val):
            """Normalisasi variasi penulisan pekerjaan dari Excel"""
            val = val.strip()
            mapping_norm = {
                'tidak bekerja': 'Tidak Bekerja',
                'tidak dapat diterapkan': 'Tidak Bekerja',
                'buruh': 'Buruh',
                'petani': 'Petani',
                'pedagang kecil': 'Pedagang Kecil',
                'pedagang': 'Pedagang Kecil',
                'peternak': 'Peternak',
                'nelayan': 'Nelayan',
                'wiraswasta': 'Wiraswasta',
                'karyawan swasta': 'Karyawan Swasta',
                'karyawan bumn': 'Karyawan BUMN',
                'pns/tni/polri': 'PNS/TNI/POLRI',
                'pns': 'PNS/TNI/POLRI',
                'tni': 'PNS/TNI/POLRI',
                'polri': 'PNS/TNI/POLRI',
                'lainnya': 'Lainnya',
                'sopir': 'Lainnya',
            }
            return mapping_norm.get(val.lower(), 'Tidak Bekerja')

        def norm_penghasilan(val):
            """Normalisasi variasi penulisan penghasilan dari Excel"""
            val = val.strip().lower()
            if 'tidak' in val or val in ['', 'nan']:
                return 'Tidak Berpenghasilan'
            if 'kurang dari' in val or '<= 500' in val or '500.000' in val and 'kurang' in val:
                return '<= Rp. 500.000'
            if '500,000' in val and '999' in val:
                return 'Rp. 500,000 - Rp. 999,999'
            if '1,000,000' in val and '1,999' in val:
                return 'Rp. 1,000,000 - Rp. 1,999,999'
            if '2,000,000' in val and '4,999' in val:
                return 'Rp. 2,000,000 - Rp. 4,999,999'
            if '5,000,000' in val or '20,000,000' in val:
                return 'Rp. 5,000,000 - Rp. 20,000,000'
            # Coba cocokkan "Kurang dari Rp. 500,000"
            if 'kurang' in val:
                return '<= Rp. 500.000'
            return 'Tidak Berpenghasilan'

        def norm_jenis_tinggal(val):
            if val is None: return list(MAPPING['Jenis_Tinggal'].keys())[0]
            v = val.lower()
            if 'orang tua' in v or 'orangtua' in v: return 'Bersama orang tua'
            if 'wali' in v: return 'Wali'
            if 'kost' in v or 'kos' in v: return 'Kost'
            if 'asrama' in v: return 'Asrama'
            # Kembalikan nilai asli jika ada di MAPPING
            if val in MAPPING['Jenis_Tinggal']:
                return val
            return list(MAPPING['Jenis_Tinggal'].keys())[0]

        def norm_kepemilikan(val):
            if val is None: return list(MAPPING['Kepemilikan_Rumah'].keys())[0]
            v = val.lower()
            if 'sendiri' in v or 'milik' in v: return 'Milik Sendiri'
            if 'sewa' in v or 'kontrak' in v: return 'Sewa'
            if val in MAPPING['Kepemilikan_Rumah']:
                return val
            return list(MAPPING['Kepemilikan_Rumah'].keys())[0]

        def norm_alat_trans(val):
            if val is None: return list(MAPPING['Alat_Transportasi'].keys())[0]
            v = val.lower()
            if 'jalan kaki' in v or 'kaki' in v: return 'Jalan kaki'
            if 'kendaraan pribadi' in v or 'pribadi' in v: return 'Kendaraan Pribadi'
            if 'angkutan umum' in v or 'umum' in v: return 'Angkutan umum'
            if 'sepeda' in v and 'motor' not in v: return 'Sepeda'
            if val in MAPPING['Alat_Transportasi']:
                return val
            return list(MAPPING['Alat_Transportasi'].keys())[0]

        def norm_kondisi(val):
            if val is None: return list(MAPPING['Kondisi_Keluarga'].keys())[0]
            v = val.lower()
            if 'lengkap' in v: return 'Lengkap'
            if 'yatim piatu' in v: return 'Yatim Piatu'
            if 'yatim' in v: return 'Yatim'
            if 'piatu' in v: return 'Piatu'
            if val in MAPPING['Kondisi_Keluarga']:
                return val
            return list(MAPPING['Kondisi_Keluarga'].keys())[0]

        def norm_kip_kps(val):
            if val is None: return list(MAPPING.get('Penerima_KIP', {'Tidak': 0}).keys())[0]
            v = str(val).lower().strip()
            if v in ['ya', 'yes', '1', 'true']: return 'Ya'
            if v in ['tidak', 'no', '0', 'false']: return 'Tidak'
            if val in MAPPING.get('Penerima_KIP', {}):
                return val
            return 'Tidak'

        # --- 5. Mapping ke kategori model ---
        final_categories = {
            "Pekerjaan_Ayah":    map_pekerjaan(norm_pekerjaan(p_ayah_raw)),
            "Penghasilan_Ayah":  map_penghasilan(norm_penghasilan(g_ayah_raw)),
            "Pekerjaan_Ibu":     map_pekerjaan(norm_pekerjaan(p_ibu_raw)),
            "Penghasilan_Ibu":   map_penghasilan(norm_penghasilan(g_ibu_raw)),
            "Jumlah_Tanggungan": map_tanggungan(tang_raw),
            "Jenis_Tinggal":     norm_jenis_tinggal(jenis_tinggal),
            "Kepemilikan_Rumah": norm_kepemilikan(kepemilikan),
            "Alat_Transportasi": norm_alat_trans(alat_trans),
            "Kondisi_Keluarga":  norm_kondisi(kondisi_kel),
            "Penerima_KIP":      norm_kip_kps(penerima_kip),
            "Penerima_KPS":      norm_kip_kps(penerima_kps),
        }

        # --- 6. Validasi semua nilai ada di MAPPING ---
        numeric_vals = {}
        for k, v in final_categories.items():
            if k not in MAPPING:
                return False
            if v not in MAPPING[k]:
                # Pakai default pertama jika tidak cocok
                v = list(MAPPING[k].keys())[0]
                final_categories[k] = v
            numeric_vals[k] = MAPPING[k][v]

        # --- 7. Prediksi ---
        hasil_prediksi = predict(numeric_vals)
        val_hasil_db   = str(hasil_prediksi)

        # --- 8. INSERT ---
        columns      = ", ".join(final_categories.keys())
        placeholders = ", ".join(["?"] * len(final_categories))
        query = f"INSERT INTO siswa (nipd, nama, {columns}, hasil, created_at) VALUES (?, ?, {placeholders}, ?, ?)"

        cursor.execute(query, (
            nipd_val,
            nama_val,
            *final_categories.values(),
            val_hasil_db,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        return True

    except Exception as e:
        return False
# =====================================================
# FUNGSI HELPER UNTUK LOGO
# =====================================================
def get_stat_data():
    try:
        df = pd.read_sql("SELECT * FROM siswa ORDER BY id DESC", conn)
        return df
    except Exception as e:
        st.error(f"Error Database: {e}")
        return pd.DataFrame()

def get_safe_data():
    try:
        # Mengambil data dengan nama kolom asli dari database
        df = pd.read_sql("SELECT * FROM siswa ORDER BY id ASC", conn)
        return df
    except Exception as e:
        st.error(f"Error Database: {e}")
        return pd.DataFrame()
# Panggil CSS
local_css("style.css")

# =====================================================
# DATABASE & MODEL LOADING
# =====================================================
curr_path = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(curr_path, 'model', 'rf_pip_model.pkl')

try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    st.error(f"Gagal memuat model: {e}")
# =====================================================
# SESSION INIT
# =====================================================
if "login" not in st.session_state: st.session_state.login = False
if "page" not in st.session_state: st.session_state.page = "login"
if "username" not in st.session_state: st.session_state.username = None
if "menu" not in st.session_state: st.session_state.menu = "Statistik PIP"

# =====================================================
# FUNGSI EXPORT
# =====================================================
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

# =====================================================
# LOGIKA MAPPING & PENERJEMAH
# =====================================================
def map_penghasilan(val):
    """Mengonversi nilai nominal ke kategori penghasilan"""
    if val == "Tidak Berpenghasilan": return "Tidak Berpenghasilan"
    elif val == "<= Rp. 500.000": return "Sangat Rendah"
    elif val == "Rp. 500,000 - Rp. 999,999": return "Rendah"
    elif val == "Rp. 1,000,000 - Rp. 1,999,999": return "Sedang"
    elif val == "Rp. 2,000,000 - Rp. 4,999,999": return "Tinggi"
    elif val == "Rp. 5,000,000 - Rp. 20,000,000": return "Sangat Tinggi"
    return "Tidak Berpenghasilan"

def map_pekerjaan(val):
    """Mengonversi jenis pekerjaan spesifik ke kategori kelompok"""
    rendah = ["Buruh", "Pedagang Kecil", "Peternak", "Nelayan"]
    menengah = ["Wiraswasta", "Karyawan Swasta", "Lainnya", "Sopir", "Pedagang"]
    tinggi = ["Karyawan BUMN", "PNS", "TNI", "POLRI", "PNS/TNI/POLRI"]
    
    if val == "Tidak Bekerja": return "Tidak Bekerja"
    if any(x in val for x in rendah): return "Rendah"
    if any(x in val for x in menengah): return "Menengah"
    if any(x in val for x in tinggi): return "Tinggi"
    return "Menengah"

def map_tanggungan(val):
    """Mengonversi jumlah orang ke kategori tanggungan"""
    if val in ["1", "2"]: return "Sedikit"
    if val in ["3", "4"]: return "Sedang"
    if val in ["5", "6"]: return "Banyak"
    return "Sedikit"

# =====================================================
# CEK TOKEN DARI URL (UNTUK RESET PASSWORD)
# =====================================================

# Ambil query parameter dari URL
try:
    query_params = st.query_params
    
    # Jika ada token di URL dan belum disimpan di session
    if "token" in query_params:
        token_from_url = query_params["token"]
        
        # Simpan token ke session state
        if "reset_token" not in st.session_state or st.session_state.reset_token != token_from_url:
            st.session_state.reset_token = token_from_url
            st.session_state.page = "reset_password"
            
except Exception as e:
    pass  # Ignore error jika query_params tidak tersedia

# =====================================================
# PAKSA SIDEBAR RENDER (AGAR HAMBURGER MUNCUL)
# =====================================================
# PENTING: Harus dipanggil SEBELUM st.stop() agar Streamlit Cloud mendeteksi sidebar
if not st.session_state.login:
    with st.sidebar:
        st.markdown("""
            <div style="text-align:center; padding:20px;">
                <h3 style="color:#1e3a8a;">🔐 Area Login</h3>
                <p style="color:#64748b; font-size:14px;">Silakan login untuk mengakses dashboard</p>
            </div>
        """, unsafe_allow_html=True)

# =====================================================
# LOGIN PAGE
# =====================================================
#Jika belum login dan bukan halaman reset, paksa ke login
if not st.session_state.login:
    if st.session_state.page == "reset_password":
        # Izinkan akses halaman reset password
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col2:
            reset_password_ui()
        st.stop()
    else:

        # HEADER KANDAS KIRI
        logo_b64 = get_base64("assets/images/logo.png")
        st.markdown(f"""
            <div class="login-header">
                <img src="data:image/png;base64,{logo_b64}" class="login-logo-small">
                <h2 class="login-main-title">
                    SELAMAT DATANG DI SISTEM KLASIFIKASI CALON PENERIMA PIP<br>
                    SMPN 12 PEMATANGSIANTAR
                </h2>
            </div>
        """, unsafe_allow_html=True)

        # LAYOUT UTAMA: BANNER KIRI KANDAS, LOGIN KANAN
        col_banner, col_spacer, col_login = st.columns([1.7, 0.1, 1.2])

        with col_banner:
                st.image("assets/images/Banner.png", use_column_width=True)

        with col_login:
            tab_admin, tab_siswa = st.tabs(["🔐 Admin", "🎓 Siswa"])
            with tab_admin:
                login_admin()
            with tab_siswa:
                st.markdown("<h3 style='text-align: center; color: #1e3a8a;'>Cek Status PIP</h3>", unsafe_allow_html=True)
                nipd_input = st.text_input("Masukkan NIPD", max_chars=6, key="cek_nipd_input")
                
                if st.button("🔍 Cek Status", key="btn_cek_status_siswa"): 
                    if not nipd_input.isdigit() or len(nipd_input) != 6:
                        st.error("NIPD harus 6 angka")
                    else:
                        data_siswa = conn.execute("SELECT nama, hasil FROM siswa WHERE nipd=?", (nipd_input,)).fetchone()
                        if not data_siswa:
                            st.warning("⚠️ Data siswa tidak ditemukan")
                        else:
                            status_teks = "LAYAK" if data_siswa["hasil"] == 1 else "TIDAK LAYAK"
                            st.success(f"👤 {data_siswa['nama']} — Status: **{status_teks}**")

        st.stop()

# =====================================================
# DASHBOARD ADMIN (SETELAH LOGIN)
# =====================================================
st.sidebar.markdown("""
    <style>
        .sidebar-header {
            text-align: center; 
            font-size: 18px; 
            font-weight: bold; 
            padding: 8px;
            background: #1e3a8a;
            color: white;
            border-radius: 8px;
            margin-bottom: 15px;
        }
    </style>
    <div class="sidebar-header">📊 MENU UTAMA</div>
""", unsafe_allow_html=True)

options = ["Statistik PIP", "Klasifikasi Siswa", "Pengaturan"]
index = options.index(st.session_state.menu) if st.session_state.menu in options else 0
menu = st.sidebar.radio("Menu Utama", options, index=index, label_visibility="collapsed")

st.sidebar.markdown("---")

if st.sidebar.button("🚪 LOGOUT", key="btn_logout_side"):
    st.session_state.login = False
    st.session_state.page = "login"
    st.rerun()

# --- HEADER DASHBOARD ---
st.markdown(f"""
    <div style="background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%); padding: 20px; border-radius: 12px; margin-bottom: 20px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.15);">
        <h1 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: 0.5px;">
            👋 SELAMAT DATANG
        </h1>
        <hr style="margin: 12px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.3);">
        <p style="margin: 0; font-size: 15px; font-weight: 500; opacity: 0.9;">
            SISTEM MANAJEMEN KLASIFIKASI PIP SMPN 12 PEMATANGSIANTAR
        </p>
    </div>
""", unsafe_allow_html=True)

# =====================================================
# MENU: STATISTIK (PERBAIKAN GRAFIK)
# =====================================================
if menu == "Statistik PIP":
    st.markdown("### 📊 Dashboard Analisis Penelitian")
        
    # 1. Ambil data langsung dari database
    df_stat = pd.read_sql("SELECT * FROM siswa", conn)

    if not df_stat.empty:
        # 2. STANDARISASI KOLOM 'hasil' → Pastikan jadi integer 0/1
        # Debugging: Lihat isi kolom hasil sebelum diproses
        # st.write("DEBUG - Isi kolom hasil:", df_stat['hasil'].unique())
            
        df_stat['hasil'] = df_stat['hasil'].astype(str).str.strip()
        df_stat['hasil'] = df_stat['hasil'].apply(
            lambda x: 1 if x in ['1', '1.0', 'LAYAK'] else 0
        )
            
        # 3. Buat label teks untuk visualisasi
        df_stat['Status_Label'] = df_stat['hasil'].apply(
            lambda x: 'LAYAK' if x == 1 else 'TIDAK LAYAK'
        )
            
        # 4. METRIK UTAMA
        total = len(df_stat)
        layak_cnt = (df_stat['hasil'] == 1).sum()
        tidak_cnt = total - layak_cnt
            
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Sampel", f"{total} Siswa")
        c2.metric("Hasil LAYAK", f"{layak_cnt}")
        c3.metric("Hasil TIDAK LAYAK", f"{tidak_cnt}")

        st.markdown("---")

        # 5. BAR CHART (Distribusi Hasil)
        st.markdown("##### 🎯 Distribusi Hasil Klasifikasi")
            
        # Hitung distribusi dengan memastikan kedua kategori muncul
        df_counts = df_stat['Status_Label'].value_counts().reset_index()
        df_counts.columns = ['Status', 'Jumlah']
            
        # PERBAIKAN: Pastikan kedua kategori ada (meski salah satu 0)
        all_status = pd.DataFrame({
            'Status': ['LAYAK', 'TIDAK LAYAK'],
            'Jumlah': [0, 0]
        })
            
        # Merge dengan data asli
        df_counts = all_status.merge(df_counts, on='Status', how='left', suffixes=('', '_y'))
        df_counts['Jumlah'] = df_counts['Jumlah_y'].fillna(df_counts['Jumlah']).astype(int)
        df_counts = df_counts[['Status', 'Jumlah']]
            
        # DEBUGGING: Tampilkan data yang akan di-plot
        # st.write("DEBUG - Data untuk grafik:", df_counts)
            
        # Buat Bar Chart dengan Plotly
        fig_bar = go.Figure()
            
        # Tambahkan bar untuk setiap status
        for idx, row in df_counts.iterrows():
            color = '#1976D2' if row['Status'] == 'LAYAK' else '#FF5252'
            fig_bar.add_trace(go.Bar(
                x=[row['Status']],
                y=[row['Jumlah']],
                name=row['Status'],
                marker_color=color,
                text=[f"{row['Jumlah']} Siswa"],
                textposition='outside',
                textfont=dict(size=14, color='black'),
                showlegend=False
            ))
            
        fig_bar.update_layout(
            title={
                'text': 'Perbandingan Siswa Layak vs Tidak Layak',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#1e3a8a'}
            },
            xaxis_title="Status Kelayakan",
            yaxis_title="Jumlah Siswa",
            xaxis=dict(
                tickfont=dict(size=12),
                categoryorder='array',
                categoryarray=['TIDAK LAYAK', 'LAYAK']  # Urutan kiri ke kanan
            ),
            yaxis=dict(
                tickfont=dict(size=12),
                range=[0, max(df_counts['Jumlah']) + 1]  # Tambah sedikit ruang di atas
            ),
            height=450,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=80, b=60, l=60, r=40)
        )
            
        # Tampilkan grafik
        st.plotly_chart(fig_bar, use_container_width=True)

    else:
        st.info("📂 Database masih kosong. Silakan input data terlebih dahulu di menu **Klasifikasi Siswa**.")

# --- MENU: KLASIFIKASI ---
elif menu == "Klasifikasi Siswa":
    nama = "" 
    nipd = ""
        
    tab_view, tab_input = st.tabs(["📋 Data Terklasifikasi", "➕ Input Klasifikasi Baru"])

    # --- TAB 1: VIEW DATA TERKLASIFIKASI ---
    with tab_view:
        
        # ===== FITUR BARU: IMPORT DATA DARI EXCEL =====
        with st.expander("📤 Import Data dari Excel", expanded=False):
            st.markdown("""
            **Format kolom Excel yang dikenali:**  
            `NIPD`, `Nama`, `Pekerjaan_Ayah`, `Penghasilan_Ayah`, `Pekerjaan_Ibu`, `Penghasilan_Ibu`,  
            `Jumlah_Tanggungan`, `Jenis_Tinggal`, `Kepemilikan_Rumah`, `Alat_Transportasi`,  
            `Kondisi_Keluarga`, `Penerima_KIP`, `Penerima_KPS`
            
            ⚠️ Kolom selain di atas akan **diabaikan**. Data akan **diklasifikasikan otomatis** oleh model.
            """)

            uploaded_file = st.file_uploader("Upload file Excel (.xlsx)", type=["xlsx"], key="uploader_import")

            if uploaded_file is not None:
                try:
                    df_import = pd.read_excel(uploaded_file)
                    # Normalisasi nama kolom: strip spasi & title-case
                    df_import.columns = [c.strip() for c in df_import.columns]

                    # ===== PERBAIKAN: Skip baris 0 jika itu sub-header =====
                    # Deteksi: jika baris pertama berisi teks seperti "Nama ", "Tahun Lahir" (bukan data nyata)
                    first_row = df_import.iloc[0]
                    nipd_first = first_row.get('NIPD') or first_row.get('nipd')
                    if nipd_first is None or str(nipd_first).strip() in ['', 'nan', 'None']:
                        df_import = df_import.iloc[1:].reset_index(drop=True)
                    # =====

                    st.write("**Preview 10 baris pertama:**")
                    st.dataframe(df_import.head(10), use_container_width=True)

                    col_imp1, col_imp2 = st.columns(2)
                    with col_imp1:
                        st.info(f"📊 Total **{len(df_import)}** baris data ditemukan.")
                    with col_imp2:
                        if st.button("✅ Konfirmasi Import & Klasifikasi", type="primary", use_container_width=True):
                            cursor      = conn.cursor()
                            success_cnt = 0
                            skip_cnt    = 0

                            # Progress bar
                            progress_bar = st.progress(0, text="Memproses data...")
                            total_rows   = len(df_import)

                            for i, (_, row) in enumerate(df_import.iterrows()):
                                ok = classify_and_insert_row(row, cursor)
                                if ok:
                                    success_cnt += 1
                                else:
                                    skip_cnt += 1
                                # Update progress setiap 10 baris
                                if i % 10 == 0 or i == total_rows - 1:
                                    progress_bar.progress(
                                        int((i + 1) / total_rows * 100),
                                        text=f"Memproses {i+1}/{total_rows}..."
                                    )

                            conn.commit()
                            st.cache_data.clear()
                            progress_bar.empty()

                            st.success(
                                f"✅ Import selesai! **{success_cnt}** data berhasil diklasifikasi & disimpan. "
                                f"**{skip_cnt}** data dilewati (duplikat/format tidak cocok)."
                            )
                            time.sleep(1)
                            st.rerun()

                except Exception as e:
                    st.error(f"Gagal membaca file: {e}")
        # ===== AKHIR FITUR IMPORT =====

        df_raw = get_safe_data()
            
        if not df_raw.empty:
            df_display = df_raw.copy()
                
            if 'hasil' in df_display.columns:
                df_display['hasil'] = df_display['hasil'].fillna(0).astype(int)
                df_display['hasil'] = df_display['hasil'].map({1: "LAYAK", 0: "TIDAK LAYAK"})
            
            id_series = df_display['id'].copy()  # simpan dulu sebelum di-rename/drop

            # Rename kolom (kecuali id, nipd, nama)
            df_display.columns = [c.replace("_", " ").title() if c not in ['id', 'nipd', 'nama'] else c for c in df_display.columns]

            # ===== TAMBAHAN: Kolom No urut mulai dari 1 (terpisah dari ID database) =====
            df_display.insert(0, "No", range(1, len(df_display) + 1))
            df_display = df_display.drop(columns=['id'])

            st.info("💡 **Tips:** Centang kolom 'Pilih' untuk menghapus data.")
            
            st.markdown("""
                <style>
                    [data-testid="stDataFrameToolbar"] 
                    [data-testid="stElementToolbar"] {
                        display: none !important;
                    }
                </style>
            """, unsafe_allow_html=True)

            df_display.insert(0, "Pilih", False)
            cols = ["Pilih"] + [c for c in df_display.columns if c != "Pilih"]
            df_display = df_display[cols]

            edited_df = st.data_editor(
                df_display,
                key="table_editor_v3",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "No": st.column_config.NumberColumn("No", disabled=True),  
                    "Pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                    "nipd": st.column_config.TextColumn("NIPD", disabled=True),
                    "nama": st.column_config.TextColumn("Nama Siswa", disabled=True),
                    "Hasil": st.column_config.TextColumn("Status Kelayakan", disabled=True)
                } ,
                disabled=["NO",  "nipd", "nama", "Hasil"],
            )
            
            st.markdown("<br>", unsafe_allow_html=True)

            # ===== LAYOUT DIPERLUAS: 3 KOLOM =====
            selected_mask = edited_df["Pilih"] == True
            selected_indices = edited_df[selected_mask].index.tolist()
            selected_ids = id_series.iloc[selected_indices].tolist()

            col_del, col_del_all, col_down, col_down_layak = st.columns(4)

            with col_del:
                if len(selected_ids) > 0:
                    if st.button(f"🗑️ Hapus {len(selected_ids)} Data", type="primary", use_container_width=True):
                        cursor = conn.cursor()
                        for id_target in selected_ids:
                            cursor.execute("DELETE FROM siswa WHERE id=?", (id_target,))
                        conn.commit()
                        st.cache_data.clear()
                        st.success("Data Berhasil Dihapus!✅")
                        st.rerun()
                else:
                    st.button("🗑️ Hapus (Pilih Data)", disabled=True, use_container_width=True)
            # ===== FITUR BARU: HAPUS SEMUA DATA =====
            with col_del_all:
                if st.button("⚠️ Hapus Semua Data", type="primary", use_container_width=True, key="btn_trigger_hapus_semua"):
                    st.session_state["confirm_delete_all"] = True
                    st.rerun()

            if st.session_state.get("confirm_delete_all", False):
                st.warning("⚠️ **Apakah Anda yakin ingin menghapus SEMUA data?** Tindakan ini tidak dapat dibatalkan!")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Ya, Hapus Semua", type="primary", use_container_width=True, key="btn_ya_hapus_semua"):
                        try:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM siswa")
                            cursor.execute("DELETE FROM sqlite_sequence WHERE name='siswa'")  # Reset auto increment
                            conn.commit()
                            st.cache_data.clear()
                            st.session_state["confirm_delete_all"] = False
                            st.success("✅ Semua data berhasil dihapus!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menghapus data: {e}")
                with col_no:
                    if st.button("❌ Batal", use_container_width=True):
                        st.session_state["confirm_delete_all"] = False
                        st.rerun()
            # ===== AKHIR HAPUS SEMUA =====
            with col_down:
                df_download = df_raw.copy()
                df_download = df_download.sort_values('id' , ascending=True)
                df_download = df_download.drop(columns=['id'])
                df_download.insert(0, 'no', range(1, len(df_download) + 1))
                if 'hasil' in df_download.columns:
                    df_download['hasil'] = df_download['hasil'].fillna(0).astype(int).map({1: "LAYAK", 0: "TIDAK LAYAK"})
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_download.to_excel(writer, index=False, sheet_name='Data_Klasifikasi_PIP')
                    
                st.download_button(
                    label="📥 Download Semua Data",
                    data=buffer.getvalue(),
                    file_name="Laporan_Klasifikasi_PIP.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True 
                )

            # ===== FITUR BARU: DOWNLOAD HANYA SISWA LAYAK =====
            with col_down_layak:
                import io
                df_layak = df_raw[df_raw['hasil'].fillna(0).astype(int) == 1].copy()
                
                if not df_layak.empty:
                    df_layak = df_layak.sort_values('nama', ascending=True).reset_index(drop=True)
                    df_layak.insert(0, 'No', range(1, len(df_layak) + 1))
                    
                    # Pilih hanya kolom yang perlu ditampilkan
                    kolom_tampil = ['No', 'nipd', 'nama', 'hasil']
                    df_layak_export = df_layak[[c for c in kolom_tampil if c in df_layak.columns]].copy()
                    
                    # Ubah nilai hasil dari angka ke teks
                    df_layak_export['hasil'] = 'LAYAK'
                    
                    # Rename kolom agar rapi
                    df_layak_export = df_layak_export.rename(columns={
                        'nipd': 'NIPD',
                        'nama': 'Nama Siswa',
                        'hasil': 'Status'
                    })
                    buffer_layak = io.BytesIO()
                    with pd.ExcelWriter(buffer_layak, engine='xlsxwriter') as writer:
                        df_layak_export.to_excel(writer, index=False, sheet_name='Siswa_Layak_PIP')
                    
                    st.download_button(
                        label=f"🏅 Download Siswa Layak ({len(df_layak)})",
                        data=buffer_layak.getvalue(),
                        file_name="Laporan_Siswa_Layak_PIP.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="secondary",
                        use_container_width=True
                    )
                else:
                    st.button("🏅 Tidak Ada Siswa Layak", disabled=True, use_container_width=True)
            # ===== AKHIR FITUR DOWNLOAD LAYAK =====

        else:
            st.info("Belum ada data siswa terdaftar.")

    # --- TAB 2: INPUT DATA ---
    with tab_input:
        st.markdown("### ✏️ Form Klasifikasi")
            
        # Bungkus semuanya dalam form
        with st.form("form_klasifikasi", clear_on_submit=True):
            # --- SEKSI 1: IDENTITAS ---
            c1, c2 = st.columns(2)
            nama = c1.text_input("Nama Lengkap Siswa", placeholder="Nama Lengkap")
            nipd = c2.text_input("NIPD (6 Digit)", max_chars=6, placeholder="00xxxx")
            st.markdown("---")

            # --- SEKSI 2: DATA ORANG TUA (MAPPING BARU) ---
            st.subheader("👨‍👩‍👧 Data Orang Tua & Keluarga")
            col_ortu1, col_ortu2 = st.columns(2)
                
            with col_ortu1:
                p_ayah_raw = st.selectbox("Pekerjaan Ayah", ["Tidak Bekerja", "Buruh", "Petani", "Pedagang Kecil", "Peternak", "Wiraswasta", "Karyawan Swasta", "Karyawan BUMN", "PNS/TNI/POLRI", "Lainnya"])
                g_ayah_raw = st.selectbox("Penghasilan Ayah/bln", ["Tidak Berpenghasilan", "<= Rp. 500.000", "Rp. 500,000 - Rp. 999,999", "Rp. 1,000,000 - Rp. 1,999,999", "Rp. 2,000,000 - Rp. 4,999,999", "Rp. 5,000,000 - Rp. 20,000,000"])
                tanggungan_raw = st.selectbox("Jumlah Tanggungan", ["1", "2", "3", "4", "5", "6"])

            with col_ortu2:
                p_ibu_raw = st.selectbox("Pekerjaan Ibu", ["Tidak Bekerja", "Buruh", "Petani", "Pedagang Kecil", "Peternak", "Wiraswasta", "Karyawan Swasta", "Karyawan BUMN", "PNS/TNI/POLRI", "Lainnya"])
                g_ibu_raw = st.selectbox("Penghasilan Ibu/bln", ["Tidak Berpenghasilan", "<= Rp. 500.000", "Rp. 500,000 - Rp. 999,999", "Rp. 1,000,000 - Rp. 1,999,999", "Rp. 2,000,000 - Rp. 4,999,999", "Rp. 5,000,000 - Rp. 20,000,000"])
            st.markdown("---")
                
            # --- SEKSI 3: KRITERIA LINGKUNGAN (6 KRITERIA SISA) ---
            st.subheader("🏠 Kondisi Lingkungan")
            kriteria_sisa = ["Jenis_Tinggal", "Kepemilikan_Rumah", "Alat_Transportasi", "Kondisi_Keluarga", "Penerima_KIP", "Penerima_KPS"]
                
            cols = st.columns(3)
            inputs_sisa = {}
            for i, f in enumerate(kriteria_sisa):
                with cols[i % 3]:
                    # Ambil pilihan dari MAPPING asli Anda
                    inputs_sisa[f] = st.selectbox(f.replace("_"," "), list(MAPPING[f].keys()))

            # --- TOMBOL PROSES ---
            st.markdown("<br>", unsafe_allow_html=True)
            _, col_mid, _ = st.columns([1, 1, 1])
            with col_mid:
                submit = st.form_submit_button("🚀 PROSES & SIMPAN", use_container_width=True)

        # --- LOGIKA DI LUAR FORM (AGAR ST.RERUN BEKERJA) ---
        if submit:
            if not nama or not nipd:
                st.error("Nama dan NIPD wajib diisi!")
            else:
                # 1. Inisialisasi variabel di luar try untuk menghindari garis kuning
                hasil_prediksi = None
                    
                try:
                    # 1. Jalankan fungsi Mapper untuk data Ayah, Ibu, & Tanggungan
                    final_categories = {
                        "Pekerjaan_Ayah": map_pekerjaan(p_ayah_raw),
                        "Penghasilan_Ayah": map_penghasilan(g_ayah_raw),
                        "Pekerjaan_Ibu": map_pekerjaan(p_ibu_raw),
                        "Penghasilan_Ibu": map_penghasilan(g_ibu_raw),
                        "Jumlah_Tanggungan": map_tanggungan(tanggungan_raw)
                    }
                    # 2. Gabungkan dengan 6 kriteria lingkungan
                    final_categories.update(inputs_sisa)

                    # 3. Ubah semua kategori teks menjadi angka untuk model RF
                    numeric_vals = {k: MAPPING[k][v] for k, v in final_categories.items()}
                        
                    # 4. Prediksi
                    hasil_prediksi = predict(numeric_vals)
                    val_hasil_db = str(hasil_prediksi) # Simpan sebagai string agar konsisten

                    # 5. Simpan ke Database (Simpan versi TEKS agar Tab View rapi)
                    columns = ", ".join(final_categories.keys())
                    placeholders = ", ".join(["?"] * len(final_categories))
                    query = f"INSERT INTO siswa (nipd, nama, {columns}, hasil, created_at) VALUES (?, ?, {placeholders}, ?, ?)"
                        
                    conn.execute(query, (
                        nipd, 
                        nama, 
                        *final_categories.values(), 
                        val_hasil_db, 
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    conn.commit()
                    # Bersihkan Cache agar statistik langsung update
                    st.cache_data.clear()

                    # 7. Tampilkan Hasil (Hanya jika hasil_prediksi berhasil didapat)
                    status_teks = 'LAYAK' if hasil_prediksi == 1 else 'TIDAK LAYAK'
                    status_color = "#10b981" if hasil_prediksi == 1 else "#ef4444"
                        
                    st.success(f"### 🎉 Berhasil Terklasifikasi!")
                    st.markdown(f"""
                        <div style="background-color: {status_color}; color: white; padding: 20px; border-radius: 10px; text-align: center; margin-top: 10px;">
                            <h3 style='margin:0;'>HASIL PREDIKSI: {status_teks}</h3>
                            <p style='margin:5px 0 0 0;'>Data {nama} (NIPD: {nipd}) telah disimpan.</p>
                        </div>
                    """, unsafe_allow_html=True)
                        
                    time.sleep(2)
                    st.session_state.menu = "Statistik PIP"
                    st.rerun()

                except Exception as e:
                    if "UNIQUE" in str(e):
                        st.error(f"Gagal: NIPD {nipd} sudah terdaftar!")
                    else:
                        st.error(f"Terjadi kesalahan: {e}")
                        
# --- MENU: PENGATURAN ---
if menu == "Pengaturan":
    st.subheader("⚙️ Pengaturan Akun")
    admin = conn.execute("SELECT * FROM admin WHERE username=?", (st.session_state.username,)).fetchone()
    email = st.text_input("Email", admin["email"], key="set_email")
    new_pass = st.text_input("Password Baru", type="password", key="set_pass")
    confirm = st.text_input("Konfirmasi Password Baru", type="password", key="set_conf")
        
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Simpan", key="btn_simpan_pengaturan"):
            if new_pass and new_pass != confirm:
                st.error("❌ Konfirmasi password tidak sama")
            else:
                final_pass = hashlib.sha256(new_pass.encode()).hexdigest() if new_pass else admin["password"]
                conn.execute("UPDATE admin SET email=?, password=? WHERE username=?", (email, final_pass, admin["username"]))
                conn.commit()
                st.success("✅ Akun berhasil diperbarui")
    with c2:
        if st.button("❌ Batal", key="btn_batal_pengaturan"):
            st.rerun()
        
# Force update - 26 January 2026
