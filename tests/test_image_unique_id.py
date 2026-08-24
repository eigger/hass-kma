from unittest.mock import MagicMock

from custom_components.kma.image import KmaRadarImage


def test_image_unique_id():
    hass = MagicMock()
    coordinator = MagicMock()
    device_info = MagicMock()

    subentry_id = "test_subentry_id"
    entity = KmaRadarImage(hass, coordinator, subentry_id=subentry_id, device_info=device_info)

    assert entity.unique_id == "test_subentry_id_radar_image"
    assert entity.device_info == device_info