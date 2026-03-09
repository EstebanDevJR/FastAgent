run:
	uvicorn app.main:app --reload

test:
	pytest -q

doctor:
	fastagent doctor --project-path .

bench:
	fastagent bench --base-url http://127.0.0.1:8000 --endpoint /chat
