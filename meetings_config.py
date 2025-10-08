# meetings_config.py
WHITELISTED_MEETINGS = {
    "859 6920 2880": {"name": "All Core Devs - Consensus (ACDC)", "owner": "Nico"},
    "842 5123 7513": {"name": "All Core Devs - Testing (ACDT)", "owner": "Nico"},
    "854 5172 3466": {"name": "All Core Devs - Execution (ACDE)", "owner": "zoom-bot"},
    "884 7930 8162": {"name": "All Core Devs - Testing (ACDT)", "owner": "zoom-bot"},
    "842 6574 5580": {"name": "FOCIL", "owner": "Nico"},
    "879 4371 9720": {"name": "RPC standards", "owner": "zoom-bot"},
    "865 3706 0608": {"name": "ePBS (EIP 7732)", "owner": "Nico"},
    "851 1464 8304": {"name": "EIP Editing Office Hour", "owner": "zoom-bot"},
    "899 1066 9821": {"name": "PQ Interop", "owner": "zoom-bot"},
    "889 0262 7473": {"name": "EIP-7928", "owner": "zoom-bot"},
    "891 5137 3845": {"name": "Trustless Agents", "owner": "zoom-bot"},
    "895 6907 7828": {"name": "L2 Interop", "owner": "Josh Rudolf"},
    "882 6983 6469": {"name": "All Core Devs - Execution (ACDE)", "owner": "Nico"},
    "837 0323 9965": {"name": "All Core Devs - Consensus (ACDC)", "owner": "Tim Beiko"},
    "871 9809 0010": {"name": "ETH simulate", "owner": "Nico"},
    "875 6921 0985": {"name": "ePBS (EIP 7732)", "owner": "Tim Beiko"},
    "864 6616 9680": {"name": "All Core Devs - Testing (ACDT)", "owner": "Matt Garnett"},
    "883 1710 1307": {"name": "EVM Resource Pricing", "owner": "Nico"},
    "831 7171 3683": {"name": "Portal", "owner": "Nico"},
    "913 4859 2283": {"name": "All Core Devs - Execution (ACDE)", "owner": "Tim Beiko"},
    "822 2793 8777": {"name": "All Wallet Devs", "owner": "Nico"},
    "857 1853 2657": {"name": "Roll Call", "owner": "Nico"},
}

# Convert to format without spaces for API calls
WHITELISTED_MEETING_IDS = [meeting_id.replace(" ", "") for meeting_id in WHITELISTED_MEETINGS.keys()]