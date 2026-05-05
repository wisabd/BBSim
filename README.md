Download the repo into one folder

To run the API:
uvicorn api-raw:app --reload f 

http://127.0.0.1:8000/health → should return {"status": "ok"}
http://127.0.0.1:8000/docs → interactive Swagger UI to test all endpoints
http://127.0.0.1:8000/decoders → lists available decoders

After making sure the Swagger RestAPI is running, to run the frontend:
Use python -m http.server 3000
