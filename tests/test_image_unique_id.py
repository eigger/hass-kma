import sys
from unittest.mock import MagicMock

# Define real mock base classes to inherit from
class MockImageEntity:
    def __init__(self, hass, verify_ssl=False):
        pass

class MockCoordinatorEntity:
    def __init__(self, coordinator):
        pass

_mock_image = MagicMock()
_mock_image.ImageEntity = MockImageEntity
sys.modules["homeassistant.components.image"] = _mock_image

_mock_update_coordinator = MagicMock()
_mock_update_coordinator.CoordinatorEntity = MockCoordinatorEntity
sys.modules["homeassistant.helpers.update_coordinator"] = _mock_update_coordinator

# Load other HA mocks
import tests.conftest
from homeassistant.core import HomeAssistant

# Import custom components
from custom_components.kma.image import KmaRadarImage
from custom_components.kma.coordinator import KmaImageCoordinator

def test_image_unique_id():
    hass = MagicMock()
    coordinator = MagicMock()
    device_info = MagicMock()
    
    unique_id = "test_subentry_id_radar_image"
    entity = KmaRadarImage(hass, coordinator, unique_id=unique_id, device_info=device_info)
    
    print("Entity unique_id:", entity.unique_id)
    assert entity.unique_id == unique_id
    assert entity.device_info == device_info
