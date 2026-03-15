# Prebuilt image package

Ovaj folder sadrži fajlove koji pomažu da se projekat pretvori u stvarni prebuilt Raspberry Pi image workflow.

## Ključni dijelovi
- `uvjerenja-firstboot-finalize.service` — oneshot servis koji nakon prvog boot-a pravi health artefakte i gasi sam sebe.
- `scripts/first_boot_finalize.sh` — piše first boot manifest i health rezultat u runtime var direktorij.
- `scripts/build_prebuilt_release_bundle.sh` — pakuje finalni release bundle za image proces.

## Preporučeni tok
1. Deploy aplikaciju na “golden” Pi.
2. Prođi setup wizard.
3. Pokreni acceptance check.
4. Pokreni `prepare_image_for_clone.sh`.
5. Napravi image/klon.
6. Na prvom boot-u kloniranog uređaja pusti setup wizard ili factory reset, zavisno od modela distribucije.
