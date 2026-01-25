import streamlit as st
import hashlib
import uuid
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

from database import conn

# =====================================================
# KONFIGURASI EMAIL (DARI secrets.toml)
# =====================================================
EMAIL_SENDER = st.secrets.get("EMAIL_SENDER", "your_email@gmail.com")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD", "your_app_password")
APP_URL = st.secrets.get("APP_URL", "http://localhost:8501")

# =====================================================
# LOGIN ADMIN
# =====================================================
def login_admin():
    st.markdown("<h4 style='color:#1e3a8a; margin-bottom:5px;'>Login Admin</h4>", unsafe_allow_html=True)
    
    username = st.text_input("Username", placeholder="Masukkan username", key="login_user")
    password = st.text_input("Password", type="password", placeholder="Masukkan password", key="login_pass")

    # Membuat tombol sejajar Kiri (Login) dan Kanan (Lupa Sandi)
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🔑 LOGIN", key="btn_login_main"):
            if username and password:
                admin_query = conn.execute("SELECT * FROM admin WHERE username=?", (username,)).fetchone()
                if admin_query:
                    hashed_input = hashlib.sha256(password.encode()).hexdigest()
                    if hashed_input == admin_query["password"]:
                        st.session_state.login = True
                        st.session_state.username = admin_query["username"]
                        st.rerun()
                    else:
                        st.error("Password salah!")
                else:
                    st.error("Username tidak ditemukan!")
            else:
                st.error("Isi semua kolom!")

    with col_btn2:
        if st.button("LUPA KATA SANDI❓", key="forgot_link_btn"):
            st.session_state.page = "reset_password"
            st.rerun()
# =====================================================
# RESET PASSWORD PAGE
# =====================================================
def reset_password_ui():
    if "reset_token" in st.session_state:
        st.markdown("<h3 style='text-align: center; color: #1e3a8a;'>Buat Password Baru</h3>", unsafe_allow_html=True)
        st.info("Token valid. Silakan masukkan password baru Anda.")

        new_pass = st.text_input("Password Baru", type="password", key="new_pass_reset")
        confirm_pass = st.text_input("Konfirmasi Password Baru", type="password", key="confirm_pass_reset")

        if st.button("💾 SIMPAN PASSWORD BARU", key="btn_save_new_pass"):
            if not new_pass or not confirm_pass:
                st.error("Password wajib diisi")
                return
            if new_pass != confirm_pass:
                st.error("Konfirmasi password tidak sama")
                return

            token_data = conn.execute(
                "SELECT username, expired_at FROM password_reset WHERE token=?",
                (st.session_state.reset_token,)
            ).fetchone()

            if not token_data or datetime.now() > datetime.fromisoformat(token_data["expired_at"]):
                st.error("Token tidak valid atau sudah kedaluwarsa")
                return

            hashed = hashlib.sha256(new_pass.encode()).hexdigest()
            conn.execute("UPDATE admin SET password=? WHERE username=?", (hashed, token_data["username"]))
            conn.execute("DELETE FROM password_reset WHERE token=?", (st.session_state.reset_token,))
            conn.commit()

            st.success("✅ Password diperbarui! Silakan login.")
            st.session_state.page = "login"
            if "reset_token" in st.session_state: del st.session_state.reset_token
            st.rerun()

    else:
        st.markdown("<h2 style='text-align:center;'>Lupa Kata Sandi</h2>", unsafe_allow_html=True)
        st.write("<p style='text-align:center;'>Masukkan email Anda untuk menerima link reset.</p>", unsafe_allow_html=True)
    
        email = st.text_input("Email Terdaftar", placeholder="contoh@gmail.com", key="input_email_reset")

        if st.button("📤 KIRIM LINK RESET", key="btn_send_reset"):
            if not email:
                st.error("Masukkan email terlebih dahulu!")
                return

            user = conn.execute("SELECT * FROM admin WHERE email=?", (email,)).fetchone()
            
            if user:
                # Proses pembuatan token hanya jika user ditemukan
                conn.execute("DELETE FROM password_reset WHERE email=?", (email,))
                token = str(uuid.uuid4())
                expired = datetime.now() + timedelta(minutes=15)
                
                conn.execute("INSERT INTO password_reset (username, email, token, expired_at) VALUES (?,?,?,?)",
                             (user["username"], email, token, expired.isoformat()))
                conn.commit()

                # Gunakan variabel APP_URL yang sudah didefinisikan sebelumnya
                # reset_link = f"{st.secrets['APP_URL']}?token={token}"
                # Jika send_email(email, reset_link): ...
                st.success(f"✅ Link reset berhasil dikirim ke {email}")
            else:
                # Jika email tidak ada, tidak akan error 'UnboundLocalError'
                st.error("Email tidak ditemukan dalam sistem kami.")

    # Tombol Kembali (di luar blok else agar selalu muncul)
    st.markdown("---")
    if st.button("⬅️ KEMBALI KE LOGIN", key="btn_back_to_login"):
        st.session_state.page = "login"
        if "reset_token" in st.session_state: del st.session_state.reset_token
        st.rerun()
# =====================================================
# FUNGSI KIRIM EMAIL
# =====================================================
def send_email(to_email: str, link: str):
    msg = EmailMessage()
    msg["Subject"] = "Reset Password - Sistem PIP SMPN 12"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    msg.set_content(f"Klik link berikut untuk reset password: {link}\nLink berlaku 15 menit.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        return True
    except:
        return False