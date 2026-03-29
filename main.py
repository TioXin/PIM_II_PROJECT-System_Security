import os
import platform
import subprocess
import json
import time
import ctypes
import sys

# Checking system OS to import winreg (Windows only library)
if platform.system() == "Windows":
    import winreg

def exibir_cabecalho():
    # Clears the terminal and displays the system header
    os.system('cls' if os.name == 'nt' else 'clear')
    print(r"""
    #################################################
    #    SISTEMA DE SEGURANÇA COMPUTACIONAL - ADS   #
    #          BLOQUEADOR DE USB E DNS v1.1         #
    #################################################
    """)

def carregar_config():
    # Loads configurations from config.json or returns default values
    if os.path.exists('config.json'):
        with open("config.json", 'r') as f:
            return json.load(f)
    return {"usb_blocked": False, "sites_blocked": []}

def salvar_config(dados):
    # Saves the current state of blocking into config.json
    with open("config.json", 'w') as f:
        json.dump(dados, f, indent=4)

def verificar_permissao():
    # Checks for Administrator (Windows) or Root (Linux) privileges
    try:
        if platform.system() == "Windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.getuid() == 0
    except:
        return False

def garantir_admin():
    # Requests elevated privileges if the script is not running as admin
    if not verificar_permissao():
        print("\n [!] Privilégios insuficientes. Solicitando elevação...")
        time.sleep(1)
        try:
            if platform.system() == "Windows":
                # Execute the script again with the 'runas' verb to trigger UAC
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            else:
                # Re-execute using sudo for Linux systems
                os.execvp("sudo", ["sudo", "python3"] + sys.argv)
        except Exception as e:
            print(f" [X] Erro ao elevar privilégios: {e}")
        sys.exit(0)

def alterar_status_usb(bloquear):
    # Core function to block/unblock USB storage devices across OS
    sistema = platform.system()
    try:
        if sistema == "Windows":
            # Modifies the Windows Registry to disable USBSTOR service (4 = Disabled, 3 = Enabled)
            chave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\USBSTOR", 0, winreg.KEY_SET_VALUE)
            valor = 4 if bloquear else 3
            winreg.SetValueEx(chave, "Start", 0, winreg.REG_DWORD, valor)
            winreg.CloseKey(chave)
        else:
            # Linux: Uses modprobe and blacklist files to manage kernel modules (usb_storage and uas)
            if bloquear:
                # Creates a blacklist file to prevent the driver from loading on boot
                comando = 'echo "blacklist usb_storage\nblacklist uas" | sudo tee /etc/modprobe.d/bloqueio_pim.conf'
                subprocess.run(comando, shell=True, check=True)
                # Forcefully removes the modules from the current running kernel
                subprocess.run(["sudo", "modprobe", "-r", "uas"], check=False)
                subprocess.run(["sudo", "modprobe", "-r", "usb_storage"], check=False)
            else:
                # Removes the blacklist and reloads the drivers
                subprocess.run(["sudo", "rm", "/etc/modprobe.d/bloqueio_pim.conf"], check=False)
                subprocess.run(["sudo", "modprobe", "usb_storage"], check=False)
                subprocess.run(["sudo", "modprobe", "uas"], check=False)
    except Exception as e:
        print(f" [X] Erro ao alterar USB: {e}")

def obter_caminho_hosts():
    # Returns the absolute path to the system's hosts file based on OS
    return r"C:\Windows\System32\drivers\etc\hosts" if platform.system() == "Windows" else "/etc/hosts"

def flush_dns():
    # Clears DNS cache to ensure host changes take effect immediately without browser restart
    sistema = platform.system()
    try:
        if sistema == "Windows":
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, shell=True)
        else:
            # For modern Linux distros (systemd-resolved)
            subprocess.run(["resolvectl", "flush-caches"], capture_output=True, check=False)
    except:
        pass

def normalizar_site(site):
    # Cleans the URL input to store only the domain name (e.g., 'www.google.com' -> 'google.com')
    return site.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip()

def atualizar_hosts():
    # Updates the system hosts file using markers for clean synchronization
    caminho = obter_caminho_hosts()
    config = carregar_config()
    sites = config['sites_blocked']
    
    # Custom markers to identify the section managed by this script
    MARCADOR_INICIO = "# === INICIO BLOQUEIO PIM ===\n"
    MARCADOR_FIM = "# === FIM BLOQUEIO PIM ===\n"

    try:
        if os.path.exists(caminho):
            with open(caminho, 'r') as f:
                linhas = f.readlines()
        else:
            linhas = []

        novas_linhas = []
        pular = False
        
        # Filtering loop: isolates and removes the existing block section between markers
        # This prevents duplicate entries and cleans up sites removed from config.json
        for linha in linhas:
            if linha == MARCADOR_INICIO:
                pular = True # Start ignoring lines found inside markers
                continue
            if linha == MARCADOR_FIM:
                pular = False # Resume adding lines after the section ends
                continue
            if not pular:
                novas_linhas.append(linha)

        # Adds the updated list from config.json between the custom markers
        if sites:
            # Ensures there is a newline before starting our section
            if novas_linhas and not novas_linhas[-1].endswith('\n'):
                novas_linhas.append('\n')
            novas_linhas.append(MARCADOR_INICIO)
            for site in sites:
                # Redirects both root domain and www subdomain to localhost
                novas_linhas.append(f"127.0.0.1 {site}\n")
                novas_linhas.append(f"127.0.0.1 www.{site}\n")
            novas_linhas.append(MARCADOR_FIM)

        # Saves the filtered and updated content back to the system file
        with open(caminho, 'w') as f:
            f.writelines(novas_linhas)

        flush_dns()
    except PermissionError:
        print(" [X] Erro de permissão ao editar arquivo hosts!")

def menu():
    # Main interface loop and logic handler
    garantir_admin()

    if platform.system() == "Windows":
        os.system('color 0a') # Sets terminal color to green for a 'security' feel on Windows

    while True:
        exibir_cabecalho()
        config = carregar_config()

        usb_status = "BLOQUEADO" if config['usb_blocked'] else "LIBERADO"
        print(f" Status USB: [{usb_status}] | Sites Bloqueados: {len(config['sites_blocked'])}")
        print("-" * 49)

        print(" [1] Gerenciar Bloqueio de USB")
        print(" [2] Bloquear Novo Site (DNS)")
        print(" [3] Desbloquear Site")
        print(" [4] Listar Sites Bloqueados")
        print(" [0] Sair do Sistema")

        escolha = input("\n Selecione uma opção: ").strip()

        if escolha == "1":
            exibir_cabecalho()
            print(" >>> MÓDULO DE SEGURANÇA USB <<<")
            print(" 1 - Bloquear Portas")
            print(" 2 - Liberar Portas")
            sub = input("\n Escolha: ").strip()

            if sub in ["1", "2"]:
                bloquear = (sub == "1")
                alterar_status_usb(bloquear)
                config['usb_blocked'] = bloquear
                salvar_config(config)
                print(f" [OK] USB {'Bloqueado' if bloquear else 'Liberado'} com sucesso!")
            input("\n Aperte [ENTER] para voltar...")

        elif escolha == "2":
            exibir_cabecalho()
            print(" >>> BLOQUEIO DE DOMÍNIO <<<")
            site = normalizar_site(input(" Digite o domínio (ex: youtube.com): "))
            if site:
                if site not in config['sites_blocked']:
                    config['sites_blocked'].append(site)
                    salvar_config(config)
                    atualizar_hosts()
                    print(f" [OK] {site} bloqueado localmente.")
                else:
                    print(f" [!] '{site}' já está na lista.")
            input("\n Aperte [ENTER] para voltar...")

        elif escolha == "3":
            exibir_cabecalho()
            print(" >>> DESBLOQUEIO DE DOMÍNIO <<<")
            site_rem = normalizar_site(input(" Domínio para remover: "))
            if site_rem in config['sites_blocked']:
                config['sites_blocked'].remove(site_rem)
                salvar_config(config)
                atualizar_hosts()
                print(f" [OK] {site_rem} removido da lista.")
            else:
                print(" [X] Site não encontrado.")
            input("\n Aperte [ENTER] para voltar...")

        elif escolha == "4":
            exibir_cabecalho()
            print(" >>> SITES BLOQUEADOS <<<")
            if not config['sites_blocked']:
                print(" [i] Nenhuma restrição ativa.")
            else:
                for i, s in enumerate(config['sites_blocked'], 1):
                    print(f"  {i}. {s}")
            input("\n Aperte [ENTER] para voltar...")

        elif escolha == "0":
            print("\n [!] Encerrando sessões de segurança...")
            time.sleep(1)
            break

if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        # Handles Ctrl+C gracefully
        sys.exit(0)