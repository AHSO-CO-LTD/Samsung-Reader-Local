"""
Test script for the Keyence AutoID SDK (SR_SDK_8_71) driven from Python via pythonnet.

The SDK (Keyence.AutoID.SDK.dll) is a .NET Framework 4.6.1 assembly, so it is
loaded into a real CLR (not just parsed) using pythonnet's "netfx" runtime.

Setup (already done once):
    python -m venv venv
    venv\\Scripts\\python.exe -m pip install pythonnet
    (Keyence.AutoID.SDK.dll / Communication.dll / VncClientControlCommon.dll
     copied from SR_SDK_8_71\\SDK\\AnyCPU into .\\sdk_libs)

Usage:
    venv\\Scripts\\python.exe test_sdk.py                        # discover readers on the network
    venv\\Scripts\\python.exe test_sdk.py --ip 192.168.0.1        # connect + send default command (LON)
    venv\\Scripts\\python.exe test_sdk.py --ip 192.168.0.1 --cmd "M_VR"
"""
import argparse
import os
import sys
import time

SDK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdk_libs")

ReaderAccessor = None
ReaderSearcher = None


def bootstrap():
    """Load the CLR and the Keyence SDK assemblies. Must run before anything else."""
    from pythonnet import load
    load("netfx")  # Keyence.AutoID.SDK.dll targets classic .NET Framework, not .NET Core
    import clr

    if SDK_DIR not in sys.path:
        sys.path.append(SDK_DIR)

    clr.AddReference("Communication")
    clr.AddReference("Keyence.AutoID.SDK")

    global ReaderAccessor, ReaderSearcher, ReaderSearchResult, Action
    from Keyence.AutoID.SDK import ReaderAccessor as _RA, ReaderSearcher as _RS, ReaderSearchResult as _RSR
    from System import Action as _Action
    ReaderAccessor, ReaderSearcher, ReaderSearchResult, Action = _RA, _RS, _RSR, _Action


def list_nics(searcher):
    nics = searcher.ListUpNic()
    print(f"Found {nics.Count} network interface(s):")
    for i, nic in enumerate(nics):
        print(f"  [{i}] {nic.NicName}  ip={nic.NicIpAddr}  mask={nic.NicIpv4Mask}  broadcast={nic.NicBroadCastIpAddr}")
    return nics


def discover_readers(nic_index=0, timeout_ms=3000):
    searcher = ReaderSearcher()
    try:
        nics = list_nics(searcher)
        if nics.Count == 0:
            print("No network interfaces found.")
            return []
        if nic_index >= nics.Count:
            print(f"--nic-index {nic_index} is out of range (only {nics.Count} NIC(s)).")
            return []

        searcher.SelectedNicSearchResult = nics[nic_index]
        searcher.TimeoutMs = timeout_ms

        found = []

        def on_found(result):
            # The SDK signals end-of-search with an empty IpAddress.
            if result.IpAddress:
                found.append((result.IpAddress, result.ReaderModel, result.ReaderName))
                print(f"  found reader: ip={result.IpAddress} model={result.ReaderModel} name={result.ReaderName}")

        print(f"\nSearching for readers on {nics[nic_index].NicIpAddr} (timeout {timeout_ms} ms)...")
        searcher.Start(Action[ReaderSearchResult](on_found))
        while searcher.IsSearching:
            time.sleep(0.2)
        print(f"Search finished. {len(found)} reader(s) found.")
        return found
    finally:
        searcher.Dispose()


def send_command(ip, cmd):
    reader = ReaderAccessor(ip)
    try:
        print(f"Connecting to {ip} (CommandPort={reader.CommandPort}, DataPort={reader.DataPort})...")
        ok = reader.Connect()
        if not ok:
            print(f"Connect failed. LastErrorInfo={reader.LastErrorInfo}")
            return
        print("Connected.")
        resp = reader.ExecCommand(cmd)
        print(f"ExecCommand({cmd!r}) -> {resp!r}")
    finally:
        reader.Disconnect()
        reader.Dispose()


def main():
    parser = argparse.ArgumentParser(description="Test Keyence AutoID SDK (SR-series reader) via pythonnet")
    parser.add_argument("--ip", help="Reader IP address to connect to directly (skips discovery)")
    parser.add_argument("--cmd", default="LON", help="Command to send with --ip (default: LON = trigger on)")
    parser.add_argument("--nic-index", type=int, default=0, help="Index of NIC to use for discovery")
    parser.add_argument("--timeout", type=int, default=3000, help="Discovery timeout in ms")
    args = parser.parse_args()

    bootstrap()

    if args.ip:
        send_command(args.ip, args.cmd)
    else:
        readers = discover_readers(args.nic_index, args.timeout)
        if readers:
            print("\nConnect to one of these with, e.g.:")
            for ip, model, name in readers:
                print(f"  venv\\Scripts\\python.exe test_sdk.py --ip {ip} --cmd LON")


if __name__ == "__main__":
    main()
