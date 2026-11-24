# RAK4631 INA228 test.7 MeshCore OTA target

Start from [test.6](../v0.4.2-ina228-test.6/) for an end-to-end version change
test. Choose the test.7 ZIP and matching JSON in the Pi MeshCore uploader.
Prepare and sign the package with the trusted signer, transfer and verify it,
then activate it. After the repeater rejoins, `pm version` should report
`0.4.2-ina228-test.7`.

Test.7 uses the same source commit and build options as test.6. Only the
application version changes. The application UF2 is provided for local USB
flashing. OTA activation requires a compatible bootloader and provisioned
pairing and signer on the repeater.
