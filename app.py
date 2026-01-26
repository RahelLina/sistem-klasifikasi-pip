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
    initial_sidebar_state="expanded"
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
# =====================================================
# FUNGSI HELPER UNTUK LOGO
# =====================================================
def get_stat_data():
    try:
        df = pd.read_sql("SELECT hasil FROM siswa", conn)
        return df
    except Exception as e:
        st.error(f"Error Database: {e}")
        return pd.DataFrame()

def get_safe_data():
    try:
        # Mengambil data dengan nama kolom asli dari database
        df = pd.read_sql("SELECT * FROM siswa ORDER BY id DESC", conn)
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
# HALAMAN RESET PASSWORD
# =====================================================
# =====================================================
# DASHBOARD ADMIN (SETELAH LOGIN)
# =====================================================
    st.sidebar.markdown("""
        <style>
            [data-testid="stSidebarNav"] {display: none;} 
            .sidebar-header {
                text-align: center; 
                font-size: 22px; 
                font-weight: bold; 
                padding: 10px;
                background: #1e3a8a;
                color: white;
                border-radius: 10px;
                margin-bottom: 20px;
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
        st.rerun()

    # --- HEADER DASHBOARD ---
    st.markdown(f"""
        <div style="background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h1 style="margin: 0; font-size: 32px; font-weight: 800; letter-spacing: 1px;">
                👋 SELAMAT DATANG
            </h1>
            <hr style="margin: 15px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.3);">
            <p style="margin: 0; font-size: 18px; font-weight: 500; opacity: 0.9;">
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
        # PERBAIKAN: Definisikan variabel nama di awal agar tidak kuning (NameError)
        nama = "" 
        nipd = ""
        
        tab_view, tab_input = st.tabs(["📋 Data Terklasifikasi", "➕ Input Klasifikasi Baru"])

        # --- TAB 1: VIEW DATA TERKLASIFIKASI ---
        with tab_view:
            df_raw = get_safe_data()
            
            if not df_raw.empty:
                df_display = df_raw.copy()
                
                if 'hasil' in df_display.columns:
                    df_display['hasil'] = df_display['hasil'].fillna(0).astype(int)
                    df_display['hasil'] = df_display['hasil'].map({1: "LAYAK", 0: "TIDAK LAYAK"})
                df_display.columns = [c.replace("_", " ").title() if c not in ['id', 'nipd', 'nama'] else c for c in df_display.columns]

                st.markdown("### 📋 Tabel Database & Aksi")
                st.info("💡 **Tips:** Centang kolom 'Pilih' untuk menghapus data.")
                
                df_display.insert(0, "Pilih", False)
                cols = ["Pilih"] + [c for c in df_display.columns if c != "Pilih"]
                df_display = df_display[cols]

                edited_df = st.data_editor(
                    df_display,
                    key="table_editor_v3",
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "nipd": st.column_config.TextColumn("NIPD", disabled=True),
                        "nama": st.column_config.TextColumn("Nama Siswa", disabled=True),
                        "hasil": st.column_config.TextColumn("Status Kelayakan", disabled=True)
                    }
                )

                st.markdown("<br>", unsafe_allow_html=True)
                col_del, col_down = st.columns(2) 

                target_col_id = "id" if "id" in edited_df.columns else "id"
                selected_ids = edited_df[edited_df["Pilih"] == True][target_col_id].tolist()

                with col_del:
                    if len(selected_ids) > 0:
                        if st.button(f"🗑️ Hapus {len(selected_ids)} Data", type="primary", use_container_width=True):
                            cursor = conn.cursor()
                            for id_target in selected_ids:
                                cursor.execute("DELETE FROM siswa WHERE id=?", (id_target,))
                            conn.commit()
                            
                            # PERBAIKAN: Refresh total agar chart di menu Statistik berubah
                            st.cache_data.clear()
                            st.success("Data Berhasil Dihapus!✅")
                            st.rerun()
                    else:
                        st.button("🗑️ Hapus (Pilih Data)", disabled=True, use_container_width=True)

                with col_down:
                    import io
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_raw.to_excel(writer, index=False, sheet_name='Data_Klasifikasi_PIP')
                    
                    st.download_button(
                        label="📥 Download Data Excel",
                        data=buffer.getvalue(),
                        file_name="Laporan_Klasifikasi_PIP.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True 
                    )
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