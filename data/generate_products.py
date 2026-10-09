"""Generate a realistic-looking product catalog as JSON Lines (standard library only).

Usage:
python -m data.generate_products # 10,000 products -> data/products.jsonl
python -m data.generate_products --count 50000 --seed 7

Names and descriptions come from hand-written templates rather than lorem-ipsum text,
so full-text search results are actually meaningful.
"""
import argparse
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

DEFAULT_OUT = Path(__file__).parent / "products.jsonl"

# (store_id, name, lat, lon) -- used for geo search later (Phase 7).
STORES = [
    ("S01", "Bengaluru Indiranagar", 12.9784, 77.6408),
    ("S02", "Bengaluru Whitefield", 12.9698, 77.7500),
    ("S03", "Chennai T. Nagar", 13.0418, 80.2341),
    ("S04", "Chennai OMR", 12.9010, 80.2279),
    ("S05", "Mumbai Andheri", 19.1136, 72.8697),
    ("S06", "Delhi Connaught Place", 28.6315, 77.2167),
    ("S07", "Hyderabad Hitech City", 17.4435, 78.3772),
    ("S08", "Pune Koregaon Park", 18.5362, 73.8940),
    ("S09", "Kolkata Park Street", 22.5535, 88.3510),
    ("S10", "Ahmedabad SG Highway", 23.0300, 72.5070),
]

CLOSERS = [
    "Ideal for everyday use.",
    "Backed by a 1-year brand warranty.",
    "A thoughtful gift for friends and family.",
    "Rated highly by customers for value for money.",
    "Ships in eco-friendly packaging.",
]

# category -> parent, price range (INR), brands {name: (price tier 0..1, [models])},
# product-type phrases, features, variant colors/sizes, tags
CATALOG = {
        "Mobiles": {
            "parent": "Electronics",
            "price": (7_000, 160_000),
            "brands": {
            "Apple": (0.95, ["iPhone 15", "iPhone 15 Pro", "iPhone 16", "iPhone 16 Pro Max"]),
            "Samsung": (0.7, ["Galaxy S24", "Galaxy S24 Ultra", "Galaxy A55", "Galaxy M35"]),
            "Google": (0.75, ["Pixel 8", "Pixel 8a", "Pixel 9 Pro"]),
            "OnePlus": (0.55, ["12", "12R", "Nord CE 4"]),
            "Xiaomi": (0.3, ["Redmi Note 13", "Redmi 13C", "14 Civi"]),
        },
        "types": ["5G Smartphone", "Smartphone", "Dual SIM Smartphone"],
        "features": ["5G connectivity", "a 120Hz AMOLED display", "a 50MP triple camera",
        "all-day battery life", "fast charging", "an IP68 water-resistant body",
        "wireless charging", "a lightweight aluminium frame"],
        "colors": ["black", "white", "blue", "green", "titanium"],
        "sizes": ["128GB", "256GB", "512GB"],
        "tags": ["5g", "camera", "dual-sim", "flagship", "budget"],
    },
    "Laptops": {
        "parent": "Electronics",
        "price": (25_000, 250_000),
            "brands": {
                "Apple": (0.95, ["MacBook Air M3", "MacBook Pro 14"]),
                "Dell": (0.6, ["Inspiron 15", "XPS 13", "Vostro 14"]),
                "HP": (0.5, ["Pavilion 15", "Victus 16", "EliteBook 840"]),
                "Lenovo": (0.5, ["IdeaPad Slim 5", "ThinkPad E14", "Legion 5"]),
                "Asus": (0.45, ["Vivobook 15", "ROG Strix G16", "Zenbook 14"]),
             },
        "types": ["Thin and Light Laptop", "Gaming Laptop", "Business Laptop", "Laptop"],
        "features": ["a 14-inch Full HD display", "16GB RAM", "a 512GB SSD", "a backlit keyboard",
        "up to 12 hours of battery", "a fingerprint reader", "Wi-Fi 6 connectivity",
        "a dedicated graphics card"],
        "colors": ["silver", "grey", "black", "blue"],
        "sizes": ["8GB/512GB", "16GB/512GB", "16GB/1TB"],
        "tags": ["work", "gaming", "student", "ultrabook"],
    },
    "Televisions": {
        "parent": "Electronics",
        "price": (12_000, 300_000),
        "brands": {
            "Samsung": (0.7, ["Crystal 4K", "Neo QLED", "The Frame"]),
            "LG": (0.7, ["OLED evo C4", "NanoCell", "UR75"]),
            "Sony": (0.85, ["Bravia X75L", "Bravia XR A80L"]),
            "TCL": (0.35, ["C645 QLED", "P635"]),
            "Xiaomi": (0.25, ["X Pro", "A Series"]),
        },
        "types": ["4K Ultra HD Smart TV", "QLED Smart TV", "LED Smart TV", "Smart Google TV"],
        "features": ["Dolby Vision and HDR10", "Dolby Atmos sound", "built-in Google TV",
        "Alexa voice control", "a 120Hz refresh rate", "screen mirroring",
        "three HDMI ports", "a bezel-less design"],
        "colors": ["black", "silver"],
        "sizes": ["43 inch", "50 inch", "55 inch", "65 inch"],
        "tags": ["4k", "smart", "home-theater"],
    },
    "Headphones": {
        "parent": "Electronics",
        "price": (800, 35_000),
        "brands": {
            "Sony": (0.8, ["WH-1000XM5", "WH-CH720N", "WF-C700N"]),
            "Bose": (0.9, ["QuietComfort Ultra", "QuietComfort 45"]),
            "JBL": (0.45, ["Tune 770NC", "Live 660NC", "Tune 520BT"]),
            "boAt": (0.15, ["Rockerz 450", "Airdopes 141", "Nirvana Ion"]),
            "Apple": (0.9, ["AirPods Pro 2", "AirPods Max"]),
        },
        "types": ["Wireless Headphones", "Noise Cancelling Headphones", "True Wireless Earbuds",
        "Bluetooth Headset"],
        "features": ["active noise cancellation", "up to 30 hours of playback", "deep bass",
        "a built-in microphone for calls", "fast charging", "multipoint Bluetooth",
        "soft memory-foam ear cushions", "a sweat-resistant design"],
        "colors": ["black", "white", "blue", "beige"],
        "sizes": ["One Size"],
        "tags": ["music", "travel", "gym", "calls"],
    },
    "Smartwatches": {
        "parent": "Electronics",
        "price": (1_500, 90_000),
        "brands": {
            "Apple": (0.95, ["Watch Series 9", "Watch SE"]),
            "Samsung": (0.7, ["Galaxy Watch 6", "Galaxy Watch FE"]),
            "Garmin": (0.85, ["Forerunner 265", "Venu 3"]),
            "Noise": (0.15, ["ColorFit Pro 5", "Halo Plus"]),
            "Amazfit": (0.3, ["GTR 4", "Bip 5"]),
        },
        "types": ["Smartwatch", "Fitness Watch", "GPS Smart Watch"],
        "features": ["heart-rate and SpO2 monitoring", "built-in GPS", "sleep tracking",
        "an always-on AMOLED display", "5ATM water resistance", "Bluetooth calling",
        "up to 10 days of battery"],
        "colors": ["black", "silver", "rose gold", "blue"],
        "sizes": ["40mm", "44mm", "46mm"],
        "tags": ["fitness", "health", "gps"],
    },
    "Running Shoes": {
        "parent": "Fashion",
        "price": (1_200, 18_000),
        "brands": {
            "Nike": (0.75, ["Pegasus 41", "Revolution 7", "Invincible 3"]),
            "Adidas": (0.7, ["Ultraboost Light", "Duramo SL", "Adizero SL"]),
            "Puma": (0.5, ["Velocity Nitro 3", "Softride"]),
            "ASICS": (0.75, ["Gel-Nimbus 26", "Gel-Kayano 31"]),
            "Campus": (0.1, ["North Plus", "Oxyfit"]),
        },
        "types": ["Running Shoes", "Men's Running Shoes", "Women's Running Shoes", "Road Running Shoes"],
        "features": ["a breathable mesh upper", "responsive foam cushioning", "a durable rubber outsole",
        "a lightweight design", "reflective details for night runs", "a padded collar"],
        "colors": ["black", "white", "grey", "blue", "red"],
        "sizes": ["UK 6", "UK 7", "UK 8", "UK 9", "UK 10", "UK 11"],
        "tags": ["running", "gym", "sports"],
    },
        "T-Shirts": {
        "parent": "Fashion",
        "price": (399, 3_500),
        "brands": {
            "Nike": (0.7, ["Dri-FIT Legend", "Sportswear Club"]),
            "Adidas": (0.65, ["Essentials 3-Stripes", "Own the Run"]),
            "Puma": (0.5, ["Essentials Logo"]),
            "Allen Solly": (0.4, ["Solid Crew Neck", "Classic"]),
            "Levi's": (0.55, ["Housemark", "Graphic Crew"]),
        },
        "types": ["Cotton T-Shirt", "Round Neck T-Shirt", "Polo T-Shirt", "Sports T-Shirt"],
        "features": ["100% cotton fabric", "a regular fit", "moisture-wicking fabric",
        "a soft, breathable feel", "a ribbed crew neck", "machine-washable fabric"],
        "colors": ["black", "white", "navy", "olive", "maroon", "grey"],
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "tags": ["casual", "cotton", "summer"],
    },
    "Coffee Makers": {
        "parent": "Home & Kitchen",
        "price": (2_000, 70_000),
        "brands": {
        "Philips": (0.5, ["HD7432", "HD7462"]),
        "De'Longhi": (0.85, ["Dedica EC685", "Magnifica S"]),
        "Morphy Richards": (0.35, ["Europa Espresso", "Fresco"]),
        "Nespresso": (0.8, ["Essenza Mini", "Vertuo Pop"]),
        "Prestige": (0.2, ["PCMD 1.0"]),
        },
        "types": ["Drip Coffee Maker", "Espresso Machine", "Capsule Coffee Machine"],
        "features": ["a 15-bar pressure pump", "a milk frother for cappuccinos", "an anti-drip function",
        "a keep-warm plate", "a removable water tank", "one-touch brewing"],
        "colors": ["black", "silver", "red"],
        "sizes": ["0.6L", "1.2L", "1.5L"],
        "tags": ["coffee", "kitchen", "gift"],
    },
    "Water Bottles": {
        "parent": "Home & Kitchen",
        "price": (199, 4_500),
        "brands": {
            "Milton": (0.3, ["Thermosteel Duo", "Aqua"]),
            "Cello": (0.2, ["Puro Steel", "Swift"]),
            "Borosil": (0.4, ["Hydra Trek", "Vacuum Flask"]),
            "Hydro Flask": (0.9, ["Standard Mouth", "Wide Mouth"]),
            "Tupperware": (0.35, ["Aquasafe"]),
        },
        "types": ["Insulated Water Bottle", "Stainless Steel Bottle", "Vacuum Flask", "Sports Bottle"],
        "features": ["double-wall vacuum insulation", "keeps drinks cold for 24 hours",
        "keeps beverages hot for 12 hours", "a leak-proof lid",
        "BPA-free food-grade steel", "a sweat-free exterior"],
        "colors": ["black", "blue", "green", "pink", "silver"],
        "sizes": ["500ml", "750ml", "1L"],
        "tags": ["travel", "gym", "office"],
    },
    "Mixer Grinders": {
        "parent": "Home & Kitchen",
        "price": (1_800, 15_000),
        "brands": {
            "Preethi": (0.5, ["Zodiac", "Blue Leaf"]),
            "Bajaj": (0.3, ["Rex", "GX 1"]),
            "Philips": (0.5, ["HL7756"]),
            "Sujata": (0.6, ["Dynamix", "Powermatic Plus"]),
            "Butterfly": (0.3, ["Jet Elite", "Smart"]),
        },
        "types": ["Mixer Grinder", "Juicer Mixer Grinder", "Mixer Grinder with 3 Jars"],
        "features": ["a powerful copper motor", "stainless steel jars", "overload protection",
        "a leak-proof jar lid", "three speed settings with pulse", "anti-skid feet"],
        "colors": ["white", "black", "red"],
        "sizes": ["500W", "750W", "1000W"],
        "tags": ["kitchen", "cooking", "appliance"],
    },
}


def make_price(lo: float, hi: float, tier: float) -> float:
    """Log-scale price around the brand's tier, ending in 9 (e.g. 12,349)."""
    log_lo, log_hi = math.log(lo), math.log(hi)
    center = log_lo + (log_hi - log_lo) * tier
    p = math.exp(random.gauss(center, 0.12 * (log_hi - log_lo)))
    p = min(hi, max(lo, p))
    return float(max(round(p, -1) - 1, 99))


def make_variants(spec: dict) -> list[dict]:
    colors = random.sample(spec["colors"], k=random.randint(1, min(3, len(spec["colors"]))))
    sizes = random.sample(spec["sizes"], k=random.randint(1, min(3, len(spec["sizes"]))))
    return [
    {"color": c, "size": s, "stock": 0 if random.random() < 0.25 else random.randint(1, 50)}
        for c in colors
        for s in sizes
    ]


def make_product(i: int, today: date) -> dict:
    category = random.choice(list(CATALOG))
    spec = CATALOG[category]
    brand = random.choice(list(spec["brands"]))
    tier, models = spec["brands"][brand]
    model = random.choice(models)
    ptype = random.choice(spec["types"])
    f1, f2, f3 = random.sample(spec["features"], 3)
    variants = make_variants(spec)

    return {
        "id": f"P{i:06d}",
        "name": f"{brand} {model} {ptype}",
        "description": (
        f"The {brand} {model} {ptype.lower()} comes with {f1}, {f2} and {f3}. "
        f"{random.choice(CLOSERS)}"
        ),
        "brand": brand,
        "category": [spec["parent"], category],
        "price": make_price(*spec["price"], tier),
        "rating": round(min(5.0, max(1.0, random.gauss(4.1, 0.5))), 1),
        "review_count": min(50_000, int(random.lognormvariate(4, 1.5))),
        "in_stock": any(v["stock"] > 0 for v in variants),
        "created_at": (today - timedelta(days=random.randint(0, 730))).isoformat(),
        "tags": random.sample(spec["tags"], k=random.randint(1, 2)),
        "variants": variants,
        "stores": [
            {"store_id": sid, "name": name, "location": {"lat": lat, "lon": lon}}
            for sid, name, lat, lon in random.sample(STORES, k=random.randint(1, 4))
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    random.seed(args.seed)
    today = date.today()
    with args.out.open("w", encoding="utf-8") as f:
        for i in range(1, args.count + 1):
            f.write(json.dumps(make_product(i, today), ensure_ascii=False) + "\n")
            print(f"Wrote {args.count:,} products to {args.out}")


if __name__ == "__main__":
    main()