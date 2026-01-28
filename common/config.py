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

        try:
            with open(filename, "r") as f:
                try:
                    return Config.model_validate_json("".join(f))
                except pydantic_core._pydantic_core.ValidationError as e:
                    print(
                        f"Failed to parse {filename}, check your changes.", file=sys.stderr
                    )
                    raise e
        except FileNotFoundError:
            print(
                f"\nError: Configuration file '{filename}' not found.\n\n"
                f"Please copy the template file to create your config:\n"
                f"  - On Linux/MacOS/Unix: cp config.json.template config.json\n"
                f"  - On Windows (Command Prompt): copy config.json.template config.json\n"
                f"  - On Windows (PowerShell): Copy-Item -Path config.json.template -Destination config.json\n\n"
                f"See the README.md for more details.\n",
                file=sys.stderr
            )
            sys.exit(1)
