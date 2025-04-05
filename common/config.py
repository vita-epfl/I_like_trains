import sys

import pydantic_core
from pydantic import BaseModel

from common.client_config import ClientConfig
from common.server_config import ServerConfig


class Config(BaseModel):
    """
    We map config.json to this class. By doing this, we:
    - make it clear which fields must appear in the config.json file
    - we have an efficient way to document the purpose of each field
    - we have an efficient way to handle default values
    - we can pass a single Config object around our codebase
    """

    client: ClientConfig
    server: ServerConfig

    def load(filename):
        """
        Loads a JSON config file and returns an instance of Config.
        note: this is a static method, call it with Config.load(...) instead
        of calling it on a Config's instance.
        """

        with open(filename, "r") as f:
            try:
                return Config.model_validate_json("".join(f))
            except pydantic_core._pydantic_core.ValidationError as e:
                print(
                    f"Failed to parse {filename}, check your changes.", file=sys.stderr
                )
                raise e
