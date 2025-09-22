# Example usage of HyperDB
# MIT License
# Copyright (c) 2025 Your Name

from memory_worker.hyperdb import HyperDB, HyperConfig
import numpy as np

class DummyEmbed:
    def __call__(self, texts):
        import numpy as np
        vecs = []
        for t in texts:
            v = np.zeros(8, dtype=np.float32)
            for tok in t.split():
                v[hash(tok) % 8] += 1
            n = np.linalg.norm(v) + 1e-8
            vecs.append(v / n)
        return np.asarray(vecs, dtype=np.float32)

if __name__ == "__main__":
    db = HyperDB(embedding_fn=DummyEmbed(), cfg=HyperConfig(rag_strategy="hybrid", top_k=3))
    docs = [
        {"user_input": "what is the weather", "bot_response": "it is sunny"},
        {"user_input": "what time is it", "bot_response": "it is noon"},
        {"user_input": "tell me a joke", "bot_response": "why did the chicken..."},
    ]
    db.add(docs)
    print(db.query("time now", top_k=2))
