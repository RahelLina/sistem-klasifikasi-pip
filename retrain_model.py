import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
import sklearn

print(f"🔧 Menggunakan scikit-learn versi: {sklearn.__version__}")

# =====================================================
# 1. LOAD DATASET ASLI DARI EXCEL
# =====================================================
excel_file = 'data/Dataset_PIP.xlsx'
data = pd.read_excel(excel_file, sheet_name='data_pip')

print(f"📊 Dataset loaded: {len(data)} baris")

# =====================================================
# 2. MAPPING DATA
# =====================================================
MAPPING = {
    "Jenis_Tinggal": {"Kost": 0, "Wali": 1, "Bersama orang tua": 2},
    "Kepemilikan_Rumah": {"Sewa": 0, "Milik Sendiri": 1},
    "Alat_Transportasi": {"Jalan kaki": 0, "Angkutan umum": 1, "Kendaraan Pribadi": 2},
    "Kondisi_Keluarga": {"Yatim Piatu": 0, "Yatim": 1, "Piatu": 2, "Lengkap": 3},
    "Jumlah_Tanggungan": {"Banyak": 0, "Sedang": 1, "Sedikit": 2},
    "Pekerjaan_Ayah": {"Tidak Bekerja": 0, "Sangat Rendah": 1, "Rendah": 2, "Menengah": 3, "Tinggi": 4},
    "Penghasilan_Ayah": {"Tidak Berpenghasilan": 0, "Sangat Rendah": 1, "Rendah": 2, "Sedang": 3, "Tinggi": 4, "Sangat Tinggi": 5},
    "Pekerjaan_Ibu": {"Tidak Bekerja": 0, "Sangat Rendah": 1, "Rendah": 2, "Menengah": 3, "Tinggi": 4},
    "Penghasilan_Ibu": {"Tidak Berpenghasilan": 0, "Sangat Rendah": 1, "Rendah": 2, "Sedang": 3, "Tinggi": 4, "Sangat Tinggi": 5},
    "Penerima_KIP": {"Tidak": 0, "Ya": 1},
    "Penerima_KPS": {"Tidak": 0, "Ya": 1}
}

print("\n🔄 Melakukan mapping data...")
for col, mapping in MAPPING.items():
    if col in data.columns:
        data[col] = data[col].map(mapping)
        print(f"  ✅ {col}: {data[col].nunique()} kategori unik")

# =====================================================
# 3. PISAHKAN FITUR DAN TARGET
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

X = data[FEATURE_ORDER]

# Target: Layak_PIP (Ya/Tidak → 1/0)
data['Layak_PIP'] = data['Layak_PIP'].map({'Ya': 1, 'Tidak': 0})
y = data['Layak_PIP'].astype(int)

print(f"\n✅ Fitur: {X.shape[1]} kolom, {X.shape[0]} baris")
print(f"✅ Target distribusi:")
print(f"   - Layak (1): {(y == 1).sum()} siswa")
print(f"   - Tidak Layak (0): {(y == 0).sum()} siswa")

# =====================================================
# 4. VALIDASI DATA
# =====================================================
print("\n🔍 Mengecek missing values...")
missing = X.isnull().sum()
if missing.sum() > 0:
    print("⚠️ Ditemukan missing values:")
    print(missing[missing > 0])
    print("\n❌ Harap perbaiki data terlebih dahulu!")
    exit(1)
else:
    print("✅ Tidak ada missing values")

# =====================================================
# 5. SPLIT DATA
# =====================================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\n📦 Data Training: {len(X_train)} baris")
print(f"📦 Data Testing: {len(X_test)} baris")

# =====================================================
# 6. TRAINING MODEL
# =====================================================
print("\n🔄 Memulai training model...")

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    max_depth=10,
    min_samples_split=5,
    min_samples_leaf=2,
)

model.fit(X_train, y_train)
print("✅ Training selesai!")

# =====================================================
# 7. EVALUASI MODEL
# =====================================================
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"\n📊 Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
print("\n📋 Classification Report:")
print(classification_report(y_test, y_pred, target_names=['TIDAK LAYAK', 'LAYAK']))

print("\n📊 Confusion Matrix:")
cm = confusion_matrix(y_test, y_pred)
print(cm)

# =====================================================
# 8. SIMPAN MODEL
# =====================================================
import os
os.makedirs('model', exist_ok=True)

joblib.dump(model, 'model/rf_pip_model.pkl')
print("\n✅ Model berhasil disimpan di 'model/rf_pip_model.pkl'")
print(f"🔧 Versi scikit-learn: {sklearn.__version__}")
print(f"📊 Total data training: {len(X_train)} baris ({len(data)} total)")
print("\n🚀 Model siap di-upload ke GitHub!")