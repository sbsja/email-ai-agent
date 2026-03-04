import base64
import json
import os
from fastapi import FastAPI, Request

app = FastAPI()

PROJECT_ID = os.environ["PROJECT_ID"]

@app.post("/pubsub/gmail")
async def gmail_push(request: Request):

    body = await request.json()

    if "message" not in body:
        return {"status": "no message"}

    message_data = body["message"]["data"]
    decoded = base64.b64decode(message_data).decode()

    notification = json.loads(decoded)

    history_id = notification["historyId"]

    print("Received Gmail notification:", history_id)

    # TODO
    # call gmail history.list
    # process messages
    # run classification
    # create labels / drafts

    return {"status": "ok"}


@app.post("/admin/renew-watch")
def renew_watch():

    # TODO
    # call Gmail users.watch API
    # store returned historyId in Firestore

    return {"status": "watch renewed"}