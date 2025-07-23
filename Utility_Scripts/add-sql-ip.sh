#!/usr/bin/env bash

# 1) If not logged in, kick off device‑code login
if ! az account show &> /dev/null; then
  echo "→ Logging you in…"
  az login --use-device-code
fi

# 2) Grab your current public IP
MYIP=$(curl -s https://ipinfo.io/ip)
echo "→ Detected IP: $MYIP"

# 3) Create/update the firewall rule
az sql server firewall-rule create \
  --resource-group  "Jobvago-RG" \
  --server          "jobvago-sqlserver-20250716" \
  --name            "ClientIP" \
  --start-ip-address $MYIP \
  --end-ip-address   $MYIP \
  --output table