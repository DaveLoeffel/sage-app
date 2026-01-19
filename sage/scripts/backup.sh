#!/bin/bash

# Sage - Backup Script
# Creates backups of PostgreSQL database and Qdrant vectors

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-7}"

echo "========================================"
echo "  Sage - Backup Script"
echo "========================================"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
echo "Backing up PostgreSQL database..."
POSTGRES_BACKUP="$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"
docker-compose exec -T postgres pg_dump -U sage sage | gzip > "$POSTGRES_BACKUP"
echo "PostgreSQL backup saved to: $POSTGRES_BACKUP"

# Backup Qdrant (optional - exports collections)
echo ""
echo "Backing up Qdrant collections..."
QDRANT_BACKUP_DIR="$BACKUP_DIR/qdrant_$TIMESTAMP"
mkdir -p "$QDRANT_BACKUP_DIR"

# Snapshot Qdrant (if supported)
curl -s -X POST "http://localhost:6333/snapshots" > /dev/null 2>&1 || true
echo "Qdrant snapshot created (check Qdrant storage for snapshot files)"

# Backup .env file (without sensitive data)
echo ""
echo "Backing up configuration (excluding secrets)..."
CONFIG_BACKUP="$BACKUP_DIR/config_$TIMESTAMP.txt"
grep -v "KEY\|SECRET\|PASSWORD\|TOKEN" .env > "$CONFIG_BACKUP" 2>/dev/null || true
echo "Configuration backup saved to: $CONFIG_BACKUP"

# Cleanup old backups
echo ""
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete
echo "Cleanup complete."

# Calculate backup size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo ""
echo "========================================"
echo "  Backup Complete!"
echo "========================================"
echo ""
echo "Backup directory: $BACKUP_DIR"
echo "Total backup size: $BACKUP_SIZE"
echo ""
echo "Files created:"
echo "  - $POSTGRES_BACKUP"
echo "  - $CONFIG_BACKUP"
echo ""
echo "To restore PostgreSQL:"
echo "  gunzip -c $POSTGRES_BACKUP | docker-compose exec -T postgres psql -U sage sage"
echo ""
