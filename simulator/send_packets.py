"""Small protocol packet sender for adapter smoke/integration work (never impersonates a live race)."""
import argparse, socket, struct, time

def main():
    p=argparse.ArgumentParser(); p.add_argument("--target",default="127.0.0.1"); p.add_argument("--port",type=int,default=12001); args=p.parse_args()
    # client event: collision with environment; vectors are valid little-endian float triplets.
    event=bytes([130,11,1])+struct.pack("<f6f",12.5,10.0,0.0,3.0,0.0,0.0,0.0)
    # car update packet used for parser/ingestion smoke checks.
    update=bytes([53,1])+struct.pack("<6f",10,0,0,2,0,0)+bytes([3])+struct.pack("<Hf",6000,.42)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        for packet in (update,event): s.sendto(packet,(args.target,args.port)); time.sleep(.1)
    print("Wysłano 2 syntetyczne pakiety; nie są danymi rzeczywistego wyścigu.")

if __name__ == "__main__": main()
