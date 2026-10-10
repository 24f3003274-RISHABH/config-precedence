import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="12-Factor Config Precedence")

# Allow the assignment page to call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

def coerce(key, value):
    value = str(value)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return value.strip().lower() in ("true", "1", "yes", "on")

    return value

def apply_layer(config, layer, prefix=""):
    for raw_key, value in layer.items():
        if value is None:
            continue

        key = str(raw_key).lower()
        if prefix:
            if not key.startswith(prefix):
                continue
            key = key[len(prefix):].lower()

        if key == "num_workers":
            key = "workers"

        if key in DEFAULTS:
            config[key] = coerce(key, value)

def get_effective_config(overrides):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML.
    env_name = os.environ.get("APP_ENV", "development")
    yaml_path = Path(f"config.{env_name}.yaml")
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        apply_layer(config, yaml_config)

    # Layer 3: .env values. Read separately so OS variables stay higher priority.
    env_file = dotenv_values(".env")
    apply_layer(config, env_file, prefix="APP_")
    if env_file.get("NUM_WORKERS") is not None:
        config["workers"] = coerce("workers", env_file["NUM_WORKERS"])

    # Layer 4: real OS environment variables with APP_ prefix.
    apply_layer(config, os.environ, prefix="APP_")

    # Highest precedence: CLI-style query overrides.
    for item in overrides:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip().lower()
        if key in DEFAULTS:
            config[key] = coerce(key, value)

    # Never reveal the actual API key.
    config["api_key"] = "****"
    return config

@app.get("/")
def root():
    return {"message": "Config precedence API is running"}

@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    return get_effective_config(set)
