import os
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM
import time
import pickle


class CommandError(Exception):
    def __init__(self, message="Invalid command."):
        self.message = message
        super().__init__(self.message)


DATA_BASE_DIR = "/home/pi/Desktop/data_base"
def send_message(sock, message, is_binary=False):
    # Serialize the message as bytes if it's not already
    data = message if is_binary else message.encode('utf-8')

    # Send message length first
    msg_len = len(data)
    sock.send(str(msg_len).encode('utf-8'))
    time.sleep(0.1)  # Small delay to allow the receiver to prepare
    
    # Send the actual message
    while data:
        sent = sock.send(data)
        data = data[sent:]


def receive_full_message(sock, as_bytes=False):
    # First, get the message length
    msg_len = int(sock.recv(10).decode('utf-8'))
    received_data = []
    bytes_left = msg_len
    while bytes_left > 0:
        chunk = sock.recv(min(bytes_left, 1024))
        received_data.append(chunk)
        bytes_left -= len(chunk)

    if as_bytes:
        return b''.join(received_data)
    else:
        return b''.join(received_data).decode('utf-8')


def connect_to_device(device_addr):
    sock = BluetoothSocket(RFCOMM)
    for port in range(1, 31):  # Try ports 1 through 30
        try:
            print("Attempting to connect on RFCOMM channel %d" % port)

            sock.connect((device_addr, port))
            return sock
        except OSError as e:
            pass
    print("Failed to connect to any port.")
    sock.close()
    return None

def receive_file(sock, file_path, file_size):
    with open(file_path, "wb") as f:
        received = 0
        while received < file_size:
            data = sock.recv(1024)
            received += len(data)
            f.write(data)
    print("File received.")

def run_via_terminal(sock):
 
    while True:
        try:
            command = input("Enter command or 'get <file>': ")
            if command == "exit":
                send_message(sock, command)
                break
            elif command.startswith("shutdown") or command.startswith("reboot"):
                send_message(sock, command)
                break
                
            else:
                interpret_command(command, sock)
        except CommandError as e:
            print(e)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            break


def interpret_command(command, sock):
    if command.startswith("add_to_queue"):  # New command to add satellite to the queue
        # Test TLE file to send
        command = command + " " + """
CSS (TIANHE)            
1 48274U 21035A   23250.60323094  .00028729  00000+0  32278-3 0  9997
2 48274  41.4752  14.6926 0010484 320.3089  39.6983 15.61907922134716
ISS (NAUKA)             
1 49044U 21066A   23250.54606199  .00010692  00000+0  19312-3 0  9994
2 49044  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414560
FREGAT DEB              
1 49271U 11037PF  23249.81523963  .00005232  00000+0  17878-1 0  9995
2 49271  51.6235  75.4294 0907707 244.0940 106.3644 12.05002786100748
CSS (WENTIAN)           
1 53239U 22085A   23250.41140741  .00030442  00000+0  34184-3 0  9998
2 53239  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836 64117
CSS (MENGTIAN)          
1 54216U 22143A   23250.41140741  .00030442  00000+0  34184-3 0  9999
2 54216  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836134683
TIANZHOU-5              
1 54237U 22152A   23250.41140741  .00030442  00000+0  34184-3 0  9992
2 54237  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836134686
SPORT                   
1 55129U 98067UW  23250.41096130  .00205883  00000+0  74258-3 0  9992
2 55129  51.6227 253.5459 0008158  53.6155 306.5601 15.87498635 39512
ISS DEB (SPX-26 IPA FSE)
1 55448U 98067VB  23250.40559372  .00070440  00000+0  58845-3 0  9990
2 55448  51.6329 265.6647 0008202  48.1999 311.9697 15.69338854 34131
SOYUZ-MS 23             
1 55688U 23024A   23250.54606199  .00010692  00000+0  19312-3 0  9991
2 55688  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414561
ARKSAT 1                
1 56311U 98067VC  23250.45811954  .00130753  00000+0  99953-3 0  9991
2 56311  51.6337 271.2656 0010179  33.9933 326.1715 15.71181175 21230
AURORASAT               
1 56312U 98067VD  23250.43613812  .00210049  00000+0  12158-2 0  9991
2 56312  51.6304 269.5906 0011389  33.4145 326.7572 15.77342685 21280
EX-ALTA-2               
1 56313U 98067VE  23250.45295770  .00134206  00000+0  10135-2 0  9996
2 56313  51.6306 271.2113 0010112  32.4133 327.7485 15.71459393 21252
LIGHTCUBE               
1 56314U 98067VF  23250.28343720  .00196505  00000+0  12223-2 0  9997
2 56314  51.6302 270.8217 0011227  27.0167 333.1415 15.75755528 21273
NEUDOSE                 
1 56315U 98067VG  23250.35576768  .00090444  00000+0  89884-3 0  9999
2 56315  51.6330 274.3316 0009599  24.9840 335.1618 15.64931275 21187
YUKONSAT                
1 56316U 98067VH  23250.30556117  .00106211  00000+0  91779-3 0  9997
2 56316  51.6326 273.2410 0010138  24.4233 335.7242 15.68321220 21218
ISS DEB                 
1 56434U 98067VJ  23250.47923682  .00067127  00000+0  72124-3 0  9996
2 56434  51.6361 275.1750 0009210  35.9259 324.2354 15.63082420 19754
TIANZHOU-6              
1 56446U 23063A   23250.41140741  .00030442  00000+0  34184-3 0  9998
2 56446  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836134680
PROGRESS-MS 23          
1 56740U 23071A   23250.54606199  .00010692  00000+0  19312-3 0  9993
2 56740  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414561
SHENZHOU-16 (SZ-16)     
1 56761U 23077A   23250.41140741  .00030442  00000+0  34184-3 0  9993
2 56761  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836134680
ISS DEB                 
1 57212U 98067VP  23250.34775579  .00032057  00000+0  48809-3 0  9994
2 57212  51.6384 280.2976 0006532  10.3926 349.7199 15.54190681 11483
1998-067VQ              
1 57312U 98067VQ  23250.57107029  .00063845  00000+0  87690-3 0  9999
2 57312  51.6380 278.7898 0005336  63.9320 296.2221 15.56691213  9824
1998-067VR              
1 57313U 98067VR  23250.51596677  .00048204  00000+0  67967-3 0  9992
2 57313  51.6384 279.1724 0003248  54.6002 305.5292 15.56111585  9827
1998-067VS              
1 57314U 98067VS  23250.49991211  .00122989  00000+0  14266-2 0  9999
2 57314  51.6330 278.3039 0006713  41.7623 318.3882 15.60861247  9824
1998-067VT              
1 57315U 98067VT  23250.50385294  .00064205  00000+0  87769-3 0  9995
2 57315  51.6374 279.0890 0005709  64.2414 295.9166 15.56813725  9826
MOONLIGHTER             
1 57316U 98067VU  23250.34141963  .00029840  00000+0  39312-3 0  9998
2 57316  51.6376 279.5056 0006521  42.0088 318.1403 15.58151988  9798
1998-067VV              
1 57317U 98067VV  23250.46616408  .00087350  00000+0  10931-2 0  9998
2 57317  51.6396 278.8447 0007100  53.9816 306.1834 15.59027884  9817
MAYA-5                  
1 57419U 98067VW  23250.26631315  .00076177  00000+0  10244-2 0  9995
2 57419  51.6368 280.4990 0009162  29.4460 330.7046 15.57152726  7788
MAYA-6                  
1 57420U 98067VX  23250.39521658  .00074601  00000+0  10057-2 0  9991
2 57420  51.6360 279.8585 0009093  29.5083 330.6420 15.57095806  7802
CYGNUS NG-19            
1 57488U 23110A   23250.54606199  .00010692  00000+0  19312-3 0  9997
2 57488  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414561
PROGRESS-MS 24          
1 57691U 23125A   23250.54606199  .00010692  00000+0  19312-3 0  9999
2 57691  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414567
CREW DRAGON 7           
1 57697U 23128A   23250.54606199  .00010692  00000+0  19312-3 0  9998
2 57697  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414563

CSS (TIANHE): 100, 2000
ISS (NAUKA): 100, 2000"""
        send_message(sock, command)
        response = receive_full_message(sock)
        print(response)

    elif command.startswith("start_tracking"):
        send_message(sock, command)
        response = receive_full_message(sock)
        print(response)

    elif command.startswith("calibrate"):
        send_message(sock, command)
        response = receive_full_message(sock)
        print(response)

    elif command.startswith("calibrate"):
        # bandwidth, centerfrequency, samplerate
        send_message(sock, command)
        response = receive_full_message(sock)
        print(response)

    elif command.startswith("getMeta"):
        send_message(sock, command)
        response = pickle.loads(receive_full_message(sock, as_bytes=True))

        # Extracting the components from the response for better readability
        current_time = response["current_time"]
        directory_files = response["data"]
        modified_schedule = response["schedule"]
        modified_processed_satellites = response["processed_schedule"]
        tracking_status = response["tracking"]

        # Print current time
        print(f"Current Time on Raspberry Pi: {current_time}")

        # Print tracking status
        print(f"Tracking Status: {'On' if tracking_status else 'Off'}\n")

        # Print list of files
        print("Directory Files:")
        for file in directory_files.split("\n"):
            print(f"- {file}")

        print("\nSchedule:")
        for satellite in modified_schedule:
            print(f"- Satellite Name: {satellite[0]}")
            print(f"  Rise Time: {satellite[1]}")
            print(f"  Set Time: {satellite[2]}\n")

        print("Processed Schedule:")
        for satellite in modified_processed_satellites:
            print(f"- Satellite Name: {satellite[0]}")
            print(f"  Rise Time: {satellite[1]}")
            print(f"  Set Time: {satellite[2]}\n")
 
    elif command.startswith("get"):
        file_path = command.split(" ", 1)[1]

        file_path = DATA_BASE_DIR + "/" + file_path
        command = "get " + file_path
        send_message(sock, command)
        response = receive_full_message(sock)
        if response == "File not found":
            print(response)
        else:
            file_size = int(response)
            destination_path = os.path.join(os.getcwd(), os.path.basename(file_path))
            receive_file(sock, destination_path, file_size)
    else:
        raise CommandError(f"'{command}' is not a recognized command.")


def main():
    # unique MAC address for Raspberry Pi (slave)
    selected_device = "E4:5F:01:FD:E5:FF"
    print("Connecting to {}".format(selected_device))
    sock = connect_to_device(selected_device)

    try:
        run_via_terminal(sock)
    except BluetoothError as e:
        print("Disconnected")
    finally:
        print("Closing socket")
        sock.close()

if __name__ == "__main__":
    main()