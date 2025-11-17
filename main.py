import asyncio
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from panoramisk.manager import Manager

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql+psycopg2://postgres:Ramusendbadmin@172.16.203.21:5432/ramusendb"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class users(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String, primary_key=True)
    username = db.Column(db.String(255))
    channel_account = db.Column(db.String(255))
    floor = db.Column(db.String(50))

ASTERISK_HOST = "172.16.203.166"
ASTERISK_PORT = 5038
ASTERISK_USERNAME = "ranatelapi"
ASTERISK_PASSWORD = "343aa1aefe4908885015295abd578b91"

def map_status_tele(status):
    mapping = {
        "0": ("Idle", "green"),
        "1": ("In Use", "orange"),
        "2": ("Busy", "red"),
        "4": ("Unavailable", "gray"),
        "8": ("Ringing", "blue"),
    }
    return mapping.get(str(status), ("Unknown", "black"))


@app.route("/api/test-simple", methods=["GET"])
def test_simple():
    """Test sederhana tanpa async"""
    print("\n" + "="*60)
    print("🧪 TEST SIMPLE DIPANGGIL")
    print("="*60)
    
    # Test 1: Ambil data dari database
    print("\n1️⃣ Mengambil data agents dari database...")
    all_agents = users.query.all()
    print(f"   ✅ Ditemukan {len(all_agents)} agents")
    
    for agent in all_agents:
        print(f"   - {agent.name}: {agent.sip}")
    
    # Test 2: Ambil data dari Asterisk
    print("\n2️⃣ Mengambil data dari Asterisk...")
    
    async def get_asterisk_data():
        manager = Manager(
            host=ASTERISK_HOST,
            port=ASTERISK_PORT,
            username=ASTERISK_USERNAME,
            secret=ASTERISK_PASSWORD,
        )
        
        try:
            await manager.connect()
            print("   ✅ Koneksi Asterisk berhasil")
            
            response = await manager.send_action({"Action": "ExtensionStateList"})
            
            extensions = []
            for msg in response:
                if hasattr(msg, "Event") and msg.Event == "ExtensionStatus":
                    exten = getattr(msg, 'Exten', '')
                    status = getattr(msg, 'Status', 'Unknown')
                    
                    # Hanya ambil yang dimulai dengan 7262
                    if exten.startswith("7262"):
                        print(f"   - Extension: {exten}, Status: {status}")
                        extensions.append({
                            "extension": exten,
                            "status": status
                        })
            
            return extensions
            
        finally:
            manager.close()
    
    asterisk_data = asyncio.run(get_asterisk_data())
    print(f"   ✅ Ditemukan {len(asterisk_data)} extensions dari Asterisk")
    
    # Test 3: Matching
    print("\n3️⃣ Mencoba matching data...")
    results = []
    
    for ext_data in asterisk_data:
        exten = ext_data['extension']
        print(f"\n   Mencari agent dengan SIP: {exten}")
        
        user = users.query.filter(users.channel_account == exten).first()
        
        if agent:
            print(f"   ✅ MATCH! Agent: {agent.name}")
            status, color = map_status_tele(ext_data['status'])
            
            results.append({
                "Extension": exten,
                "Status": status,
                "StatusCode": ext_data['status'],
                "Color": color,
                "Name": agent.name,
                "AgentID": agent.id
            })
        else:
            print(f"   ❌ TIDAK MATCH - agent tidak ditemukan di database")
    
    print(f"\n✅ Total hasil: {len(results)}")
    print("="*60 + "\n")
    
    return jsonify({
        "total_agents_in_db": len(all_agents),
        "total_extensions_in_asterisk": len(asterisk_data),
        "total_matched": len(results),
        "results": results
    })


@app.route("/api/active_channels", methods=["GET"])
def api_active_channels():
    """Endpoint utama untuk get active channels"""
    print("\n" + "🌐"*30)
    print("📍 ENDPOINT /api/active_channels DIPANGGIL")
    print("🌐"*30 + "\n")
    
    async def get_active_channels():
        manager = Manager(
            host=ASTERISK_HOST,
            port=ASTERISK_PORT,
            username=ASTERISK_USERNAME,
            secret=ASTERISK_PASSWORD,
        )
        
        try:
            print("📡 Connecting to Asterisk...")
            await manager.connect()
            print("✅ Connected!")
            
            response = await manager.send_action({"Action": "ExtensionStateList"})
            
            results = []
            count = 0
            
            for msg in response:
                if hasattr(msg, "Event") and msg.Event == "ExtensionStatus":
                    count += 1
                    exten = getattr(msg, 'Exten', '')
                    status_code = getattr(msg, 'Status', 'Unknown')
                    context = getattr(msg, 'Context', 'Unknown')
                    
                    print(f"\n{count}. Extension: {exten}")
                    print(f"   Status: {status_code}")
                    print(f"   Context: {context}")
                    
                    # Filter hanya extension yang dimulai dengan 7262
                    if not exten.startswith("7262"):
                        print(f"   ❌ SKIP: Tidak dimulai dengan 7262")
                        continue
                    
                    print(f"   ✅ PASS filter")
                    
                    # Query database
                    print(f"   🔍 Query database untuk SIP: {exten}")
                    user = users.query.filter(users.channel_account == exten).first()
                    
                    if user:
                        print(f"   ✅ MATCH! Agent: {user.username} (ID: {user.id})")
                        status, color = map_status_tele(status_code)
                        
                        results.append({
                            "Extension": exten,
                            "Context": context,
                            "Status": status,
                            "StatusCode": status_code,
                            "Color": color,
                            "Name": user.username,
                            "AgentID": user.id
                        })
                    else:
                        print(f"   ❌ NO MATCH: Agent tidak ditemukan di database")
            
            print(f"\n📊 Total hasil: {len(results)}")
            return results
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
            
        finally:
            manager.close()
            print("🔌 Connection closed\n")
    
    data = asyncio.run(get_active_channels())
    return jsonify(data)


@app.route("/api/debug/agents", methods=["GET"])
def debug_agents():
    """Cek data agents"""
    all_agents = users.query.all()
    return jsonify([
        {
            "id": agent.id,
            "name": agent.username,
            "sip": agent.channel_account
        }
        for agent in all_agents
    ])


if __name__ == "__main__":
    print("\n🚀 Starting Flask...")
    print(f"Database: ploonkdb")
    print(f"Asterisk: {ASTERISK_HOST}:{ASTERISK_PORT}\n")
    
    app.run(debug=True, host="0.0.0.0", port=5000)