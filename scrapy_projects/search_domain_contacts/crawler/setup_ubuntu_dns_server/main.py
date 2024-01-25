import subprocess


def install_dns_software(software='bind9'):
    subprocess.run(['sudo', 'apt-get', 'update'], check=True)
    subprocess.run(['sudo', 'apt-get', 'install', '-y', software], check=True)
    print(f'{software} has been installed.')


def configure_local_caching(
        dns_software='bind9',
        upstream_dns=[
            '208.67.222.222',
            '208.67.220.220',
            '208.67.222.220',
            '8.8.8.8',
            '1.1.1.1',
            '84.200.69.80',
            '9.9.9.9'
        ]):
    if dns_software == 'bind9':
        config_lines = [
            'options {',
            '    directory "/var/cache/bind";',
            '    forwarders {',
            '        ' + '; '.join(upstream_dns) + ';',
            '    };',
            '    recursion yes;',
            '    allow-query { any; };',
            '};'
        ]
        config_content = '\n'.join(config_lines)
        with open('/etc/bind/named.conf.options', 'w') as conf_file:
            conf_file.write(config_content)
    elif dns_software == 'unbound':
        # Add equivalent Unbound configuration here
        pass

    subprocess.run(['sudo', 'service', dns_software, 'restart'], check=True)
    print(f'{dns_software} has been configured and restarted.')


def test_dns_resolution(test_domain='example.com'):
    result = subprocess.run(
        ['dig', '@localhost', test_domain], stdout=subprocess.PIPE, text=True)
    print(result.stdout)


# Automation script execution
dns_software_choice = 'bind9'  # or 'unbound'
# Upstream DNS servers (OpenDNS in this case)
upstream_servers = ['208.67.222.222', '208.67.220.220']

install_dns_software(dns_software_choice)
configure_local_caching(dns_software=dns_software_choice,
                        upstream_dns=upstream_servers)
test_dns_resolution()
