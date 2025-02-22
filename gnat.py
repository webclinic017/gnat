import sys
import time
import threading
import datetime as dt
from typing import List

from gnat_ui import setup_dash
from gnat_algo import GNAT_Algo

import yaml
from harvest.trader import LiveTrader
from harvest.api.dummy import DummyStreamer
from harvest.api.paper import PaperBroker
from harvest.api.yahoo import YahooStreamer
from harvest.api.polygon import PolygonStreamer

try:
    from harvest.api.alpaca import Alpaca
except:

    def Alpaca(x, y, z):
        print("Please install 'alpaca-trade-api'")


from harvest.storage.csv_storage import CSVStorage


def start_harvest(assets: List[str], algo, storage, streamer, broker):
    trader = LiveTrader(streamer=streamer, storage=storage, broker=broker, debug=True)
    trader.set_symbol(assets)
    trader.set_algo(gnat_algo)
    # Update every minute
    trader.start("1MIN", all_history=False)


def start_dash(tickers, tickers_lock):
    # Wait for the tickers to be populated
    tickers_lock.acquire()
    while len(tickers.keys()) == 0:
        tickers_lock.release()
        time.sleep(5)
        tickers_lock.acquire()
    tickers_lock.release()

    # Start Dash
    setup_dash(tickers, tickers_lock)


def valid_cmd(cmd: str):
    """
    Returns true if the given command is valid.
    Valid commads are of the form:
        ACTION TICKER AMOUNT
    """
    if cmd in ("q" or "quit"):
        return False

    tokens = cmd.split(" ")

    if len(tokens) != 3:
        print("Incorrect format: require ACTION TICKER AMOUNT")
        return False

    if tokens[0] not in ("buy", "sell"):
        print("ACTION is not either 'buy' or 'sell'")
        return False

    try:
        int(tokens[2])
    except:
        print("AMOUNT not an integer")
        return False

    if int(tokens[2]) <= 0:
        print("AMOUNT is not positive")
        return False

    return True


def get_input(user_cmds, lock):
    cmd = ""
    print("Type 'q' or 'quit' to exit.")
    while cmd not in ("q", "quit"):
        print("Enter a command:")
        cmd = input()
        if valid_cmd(cmd):
            self.lock.acquire()
            user_cmds.append(cmd)
            self.lock.release()

    print("Goodbye!")


def init_harvest_classes(
    streamer: str,
    broker: str,
    secret_path: str,
    basic_account: str,
    alpaca_paper_trader: str,
):
    if streamer == "dummy":
        streamer_cls = DummyStreamer(dt.datetime.now())
    elif streamer == "yahoo":
        streamer_cls = YahooStreamer()
    elif streamer == "polygon":
        if basic_account is None:
            print("Is your account a basic account? (y/n)")
            basic_account = input()
        streamer_cls = PolygonStreamer(secret_path, basic_account == "y")
    elif streamer == "alpaca":
        if basic_account is None:
            print("Is your account a basic account? (y/n)")
            basic_account = input()
        if alpaca_paper_trader is None:
            print("Do you want to use Alpaca's paper trader? (y/n)")
            alpaca_paper_trader = input()
        streamer_cls = Alpaca(
            secret_path, basic_account == "y", alpaca_paper_trader == "y"
        )

    if streamer_cls is None:
        exit()

    if streamer == broker:
        return streamer_cls, streamer_cls

    if broker == "paper":
        broker_cls = PaperBroker(secret_path, streamer_cls)
    elif broker == "alpaca":
        if basic_account is None:
            print("Is your account a basic account? (y/n)")
            basic_account = input()
        if alpaca_paper_trader is None:
            print("Do you want to use Alpaca's paper trader? (y/n)")
            alpaca_paper_trader = input()
        streamer_cls = Alpaca(
            secret_path, basic_account == "y", alpaca_paper_trader == "y"
        )

    if broker_cls is None:
        exit()

    return streamer_cls, broker_cls


if __name__ == "__main__":
    basic_account = None
    alpaca_paper_trader = None

    # Check for configuration
    if len(sys.argv) == 2:
        with open(sys.argv[1], "r") as file:
            config = yaml.safe_load(file)
            assets = config["assets"]
            streamer = config["streamer"]
            broker = config["broker"]
            secret_path = config.get("secret_path", None)
            basic_account = config.get("basic_account", None)
            alpaca_paper_trader = config.get("alpaca_paper_trader", None)
    else:
        # Get assets
        print(
            "List your assets' ticker with comma seperation. For cryptos, prefex the ticker with an '@' (e.g @DOGE)."
        )
        assets = input()

        # Get Harvest configuration
        print("Pick a streamer: dummy, yahoo, polygon, alpaca.")
        streamer = input()
        print("Pick a broker: paper, alpaca.")
        broker = input()
        print("Path to secret.yaml if needed.")
        secret_path = input()

    assets = [asset.strip() for asset in assets.split(",")]
    secret_path = None if secret_path == "" else secret_path
    streamer, broker = init_harvest_classes(
        streamer, broker, secret_path, basic_account, alpaca_paper_trader
    )

    # Store the OHLC data in a folder called `gnat_storage` with each file stored as a csv document
    csv_storage = CSVStorage(save_dir="gnat_storage")

    # Init the GNAT algo and get the dash thread
    gnat_algo = GNAT_Algo()
    # Start Harvest
    harvest_thread = threading.Thread(
        target=start_harvest,
        args=(assets, gnat_algo, csv_storage, streamer, broker),
        daemon=True,
    ).start()

    # Start Dash
    dash_thread = threading.Thread(
        target=start_dash, args=(gnat_algo.tickers, gnat_algo.tickers_lock), daemon=True
    ).start()

    # Listen for user input
    get_input(gnat_algo.user_cmds, gnat_algo.user_cmds_lock)
