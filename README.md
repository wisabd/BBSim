Download the repo into one folder

To run the API:
uvicorn api-raw:app --reload f 

http://127.0.0.1:8000/health → should return {"status": "ok"}
http://127.0.0.1:8000/docs → interactive Swagger UI to test all endpoints
http://127.0.0.1:8000/decoders → lists available decoders

After making sure the Swagger RestAPI is running, to run the frontend:
Use python -m http.server 3000




For API simulation 
Input: curl -X 'POST' \
  'http://127.0.0.1:8000/simulate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "F": 1,
  "W": 1,
  "code": {
    "a1": [
      3
    ],
    "a23": [
      1,
      2
    ],
    "b12": [
      1,
      2
    ],
    "b3": [
      3
    ],
    "ell": 6,
    "m": 6
  },
  "decoders": [
    "BPOSD",
    "BP"
  ],
  "error_rate": 0.01,
  "method": 0,
  "num_repeat": 12,
  "num_trials": 10000,
  "z_basis": false
}'


Output was <img width="2844" height="1094" alt="image" src="https://github.com/user-attachments/assets/b664f5af-69a2-4279-bb95-2e7403f9680e" />



Simulation's frontend that uses the API
<img width="2938" height="1662" alt="image" src="https://github.com/user-attachments/assets/2bfc734c-4b3b-46cd-94a3-88ba1267d1ce" />

