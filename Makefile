.PHONY: dev fe be mock stop

BE_DIR  := backend
FE_DIR  := frontend
BE_PID  := .be.pid
FE_PID  := .fe.pid

dev:
	@./dev.sh

be:
	@echo "[be] starting FastAPI on :8000"
	@cd $(BE_DIR) && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

fe:
	@echo "[fe] starting Vite dev server"
	@cd $(FE_DIR) && npm run dev

mock:
	podman run --rm -p 8080:8080 \
		-v ./$(BE_DIR)/wiremock/__files:/home/wiremock/__files:ro \
		-v ./$(BE_DIR)/wiremock/mappings:/home/wiremock/mappings:ro \
		wiremock/wiremock:latest

stop:
	@[ -f $(BE_PID) ] && kill $$(cat $(BE_PID)) 2>/dev/null && rm $(BE_PID) && echo "[be] stopped" || true
	@[ -f $(FE_PID) ] && kill $$(cat $(FE_PID)) 2>/dev/null && rm $(FE_PID) && echo "[fe] stopped" || true
