from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import pickle
import faiss
from transformers import pipeline

# ===========================
# 1. LOAD & CHUNK THE PDF
# ===========================
pdf_path ="D:\my codes\Depi Project\The Project #F\Emotion_Guide_Unique_V2.pdf"
reader = PdfReader(pdf_path)

texts = [page.extract_text() for page in reader.pages if page.extract_text()]

chunk_size = 800
chunk_overlap = 100
chunks = []

for text in texts:
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap

print(f"Total chunks created: {len(chunks)}")


# ===========================
# 2. EMBEDDINGS (MiniLM - 90MB)
# ===========================
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

print("Embedding chunks...")
embeddings = embed_model.encode(chunks, show_progress_bar=True)

# Save embeddings for reuse
np.save("embeddings.npy", embeddings)
with open("chunks.pkl", "wb") as f:
    pickle.dump(chunks, f)


# ===========================
# 3. BUILD FAISS INDEX
# ===========================
embedding_dim = embeddings.shape[1]
index = faiss.IndexFlatL2(embedding_dim)
index.add(embeddings)

# Save FAISS index
faiss.write_index(index, "faiss_index.index")


# ===========================
# 4. SEARCH USING MOOD
# ===========================
mood = "stressed"
query = f"Suggest exercises, activities, and health tips for someone who is {mood}"

query_embedding = embed_model.encode([query])

k = 5  # number of results
D, I = index.search(query_embedding, k)

with open("chunks.pkl", "rb") as f:
    all_chunks = pickle.load(f)

results = [all_chunks[i] for i in I[0]]

print("\nTop Relevant Chunks:")
for i, r in enumerate(results, 1):
    print(f"\n---- Chunk {i} ----\n{r}\n")


# ===========================
# 5. SMALL SUMMARIZER (250MB)
# ===========================
summarizer = pipeline("summarization", model="facebook/bart-base")

merged_text = " ".join(results)

summary = summarizer(
    merged_text,
    max_length=150,
    min_length=40,
    do_sample=True
)

print("\n======== FINAL SUMMARY ========")
print(summary[0]['summary_text'])
