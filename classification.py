import pandas as pd
import joblib

# ===== TAMBAHKAN PATCH COMPATIBILITY =====
from sklearn.tree import DecisionTreeClassifier
import sklearn

# Patch untuk menangani model yang ditraining dengan versi lebih baru
if not hasattr(DecisionTreeClassifier, 'monotonic_cst'):
    print(f"⚠️ Warning: scikit-learn {sklearn.__version__} tidak support monotonic_cst")
    DecisionTreeClassifier.monotonic_cst = None
# =====================================================
# LOAD MODEL
# =====================================================
try:
    model = joblib.load("model/rf_pip_model.pkl")
except Exception as e:
    print(f"Error loading model: {e}")

# =====================================================
# URUTAN FITUR (HARUS SAMA SAAT TRAINING)
# =====================================================
FEATURE_ORDER = [
    "Jenis_Tinggal",
    "Kepemilikan_Rumah",
    "Alat_Transportasi",
    "Kondisi_Keluarga",
    "Jumlah_Tanggungan",
    "Pekerjaan_Ayah",
    "Penghasilan_Ayah",
    "Pekerjaan_Ibu",
    "Penghasilan_Ibu",
    "Penerima_KIP",
    "Penerima_KPS",
]

# =====================================================
# MAPPING (TEXT → NUMERIC)
# =====================================================
MAPPING = {
    "Jenis_Tinggal": {
        "Kost": 0,
        "Wali": 1,
        "Bersama orang tua": 2
    },
    "Kepemilikan_Rumah": {
        "Sewa": 0,
        "Milik Sendiri": 1
    },
    "Alat_Transportasi": {
        "Jalan kaki": 0,
        "Angkutan umum": 1,
        "Kendaraan Pribadi": 2
    },
    "Kondisi_Keluarga": {
        "Yatim Piatu": 0,
        "Yatim": 1,
        "Piatu": 2,
        "Lengkap": 3
    },
    "Jumlah_Tanggungan": {
        "Banyak": 0,
        "Sedang": 1,
        "Sedikit": 2
    },
    "Pekerjaan_Ayah": {
        "Tidak Bekerja": 0,
        "Sangat Rendah": 1,
        "Rendah": 2,
        "Menengah": 3,
        "Tinggi": 4
    },
    "Penghasilan_Ayah": {
        "Tidak Berpenghasilan": 0,
        "Sangat Rendah": 1,
        "Rendah": 2,
        "Sedang": 3,
        "Tinggi": 4,
        "Sangat Tinggi": 5
    },
    "Pekerjaan_Ibu": {
        "Tidak Bekerja": 0,
        "Sangat Rendah": 1,
        "Rendah": 2,
        "Menengah": 3,
        "Tinggi": 4
    },
    "Penghasilan_Ibu": {
        "Tidak Berpenghasilan": 0,
        "Sangat Rendah": 1,
        "Rendah": 2,
        "Sedang": 3,
        "Tinggi": 4,
        "Sangat Tinggi": 5
    },
    "Penerima_KIP": {
        "Tidak": 0,
        "Ya": 1
    },
    "Penerima_KPS": {
        "Tidak": 0,
        "Ya": 1
    }
}

# =====================================================
# REVERSE MAPPING (NUMERIC → TEXT)
# =====================================================
REVERSE_MAPPING = {
    fitur: {v: k for k, v in pilihan.items()}
    for fitur, pilihan in MAPPING.items()
}

# =====================================================
# PREDIKSI (INPUT SUDAH NUMERIK)
# =====================================================
def predict(numeric_input: dict) -> int:
    """
    Mengonversi dictionary input menjadi DataFrame sesuai FEATURE_ORDER
    lalu melakukan prediksi.
    """
    # Pastikan data dikirim berdasarkan urutan kolom yang benar
    data_for_prediction = [[numeric_input[f] for f in FEATURE_ORDER]]
    
    X = pd.DataFrame(data_for_prediction, columns=FEATURE_ORDER)

    # Melakukan prediksi
    hasil = model.predict(X)[0]
    
    return int(hasil)