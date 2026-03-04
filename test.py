import pickle

with open("token.pkl", "rb") as f:
    creds = pickle.load(f)

print("REFRESH TOKEN:")
print(creds.refresh_token)