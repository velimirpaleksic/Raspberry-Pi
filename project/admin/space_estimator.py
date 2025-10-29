# admin/space_estimator.py
def estimate_entries_per_size(
    id=8, timestamp=14, 

    ime=50, roditelj=50, 
    godina=4, mjesec=2, dan=2,

    mjesto=50, opstina=50, 
    
    razred=10, struka=100, razlog=50
):
    # rough estimate: sum of all fields in bytes
    per_entry_bytes = (
        id + timestamp +
        ime + roditelj +
        godina + mjesec + dan +
        mjesto + opstina +
        razred + struka + razlog
    )
    
    # add overhead for SQLite row (~10-20 bytes)
    per_entry_bytes += 20

    MB = 1024 * 1024
    GB = 1024 * 1024 * 1024

    return {
        "per_entry_bytes": per_entry_bytes,
        "entries_per_mb": MB // per_entry_bytes,
        "entries_per_gb": GB // per_entry_bytes,
        "entries_per_4gb": 4 * GB // per_entry_bytes
    }

if __name__ == "__main__":
    r = estimate_entries_per_size()
    print(r)