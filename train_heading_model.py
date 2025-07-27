import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

df = pd.read_csv("labeled_spans_headings_sample.csv")
X = df[["size","bold","is_caps","length","section_number_pattern","y0","x0","keyword"]]
y = df["label"]

model = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=42)
model.fit(X, y)
joblib.dump(model, "heading_model.pkl")
print("Model saved as heading_model.pkl")