import json, re
from pathlib import Path
j = json.loads((Path(__file__).resolve().parent / 'hardware-evidence.json').read_text(encoding='utf-8'))
pat = re.compile(r'(^/memory|^/timer|interrupt-controller@|ufshc|serial@|uart|mdss_mdp@|mdss_dsi[01]@|/firmware|/psci|/cpus($|/cpu@)|senna_bc_nt37705_1240_2772_dsc_cmd$|synaptics_tcm@0$)', re.I)
for n in j['nodes']:
    if not pat.search(n['path']):
        continue
    print('\nNODE', n['path'])
    for key in ['compatible','device_type','reg','reg-names','interrupts','interrupts-extended','interrupt-parent','#interrupt-cells','enable-method','cpu-release-addr','method','status','qcom,msm-id','qcom,board-id','qcom,dsi-ctrl-phandle','qcom,mdss-dsi-panel-name','oplus,mdss-dsi-vendor-name','qcom,mdss-dsi-panel-width','qcom,mdss-dsi-panel-height','qcom,mdss-dsi-panel-physical-width','qcom,mdss-dsi-panel-physical-height']:
        if key not in n['properties']:
            continue
        v = n['properties'][key]
        print(' ', key, 'strings='+repr(v.get('strings')) if 'strings' in v else '', 'u32='+repr(v.get('u32_be')) if key not in ['reg'] else '', 'decoded='+repr(v.get('decoded')) if key == 'reg' else '', 'hex='+v['hex'] if key in ['interrupt-parent','qcom,dsi-ctrl-phandle'] else '')
print('\nROOT PROPERTIES')
for k,v in j['root'].items():
    print(k, v.get('strings', v.get('u32_be', v['hex'])))
print('\nRESERVED MEMORY COUNT', sum(1 for n in j['nodes'] if n['path'].startswith('/reserved-memory/')))