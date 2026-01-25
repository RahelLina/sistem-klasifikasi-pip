# ==========================================
# MODEL FINAL RANDOM FOREST - PIP
# KONSISTEN DENGAN EKSPERIMEN
# ==========================================

import os
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier

# ==========================================
# PATH
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "Dataset_PIP.xlsx")
MODEL_PATH = os.path.join(BASE_DIR, "rf_pip_model.pkl")

# ==========================================
# LOAD DATA
# ==========================================
data = pd.read_excel(DATA_PATH, sheet_name="data_pip")

# ==========================================
# SELEKSI FITUR
# ==========================================
# Seleksi fitur
FEATURE_COLUMNS = [
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
    "Penerima_KPS"
]
TARGET_COLUMN = "Layak_PIP"

# ==========================================
# MAPPING MANUAL (SAMA DENGAN EKSPERIMEN)
# ==========================================
mapping_dict = {
    'Jenis_Tinggal': {'Kost': 0, 'Wali': 1, 'Bersama orang tua': 2},
    'Kepemilikan_Rumah': {'Sewa': 0, 'Milik Sendiri': 1},
    'Alat_Transportasi': {'Jalan kaki': 0, 'Angkutan umum': 1, 'Kendaraan Pribadi': 2},
    'Kondisi_Keluarga': {'Yatim Piatu': 0, 'Yatim': 1, 'Piatu': 2, 'Lengkap' : 3},
    'Jumlah_Tanggungan':{'Banyak': 0, 'Sedang': 1, 'Sedikit' : 2},
    'Pekerjaan_Ayah':{'Tidak Bekerja': 0,'Sangat Rendah': 1, 'Rendah': 2, 'Menengah': 3, 'Tinggi': 4},
    'Penghasilan_Ayah':{'Tidak Berpenghasilan': 0,'Sangat Rendah': 1, 'Rendah': 2, 'Sedang' :3, 'Tinggi' : 4, 'Sangat Tinggi': 5},
    'Pekerjaan_Ibu':{'Tidak Bekerja': 0,'Sangat Rendah': 1, 'Rendah': 2, 'Menengah': 3, 'Tinggi':4},
    'Penghasilan_Ibu':{'Tidak Berpenghasilan': 0, 'Sangat Rendah': 1, 'Rendah': 2, 'Sedang' :3, 'Tinggi' : 4, 'Sangat Tinggi': 5},
    'Penerima_KIP':{'Tidak': 0, 'Ya': 1},
    'Penerima_KPS':{'Tidak': 0, 'Ya': 1},
    'Layak_PIP':{'Tidak': 0, 'Ya': 1}
}
# Menerapkan mapping ke dataset
for col, mapping in mapping_dict.items():
    data[col] = data[col].map(mapping)

# ==========================================
# FEATURE & TARGET
# ==========================================
X = data[FEATURE_COLUMNS]
y = data[TARGET_COLUMN]

# ==========================================
# TRAIN MODEL FINAL (SEMUA DATA)
# ==========================================
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42
)

model.fit(X, y)

# ==========================================
# SIMPAN MODEL
# ==========================================
joblib.dump(model, MODEL_PATH)

print("===================================")
print("✅ MODEL FINAL BERHASIL DIBUAT")
print("📁 Lokasi:", MODEL_PATH)
print("===================================")
