"""
Module for interpreting the status return by several Brother label printers.
"""

import struct
import time

from attr import attrs, attrib

import brother_ql.backends
import brother_ql.labels
import brother_ql.models

class StatusValueEnum(type):
    """
    This meta-class represents an enum-like type that can additionaly represent
    unknown values.
    """
    @classmethod
    def __prepare__(metacls, cls, bases):
        return dict()

    def __new__(metacls, cls, bases, classdict):
        enum_class = super().__new__(metacls, cls, bases, classdict)
        enum_class.__new__ = metacls.__get_member__
        enum_class._member_names_ = []
        enum_class._value2member_map_ = {}

        for member_name, value in classdict.items():
            if member_name[0] == '_':
                continue

            (code, description) = value

            enum_member = object.__new__(enum_class)
            enum_member.name = member_name
            enum_member.value = code
            enum_member.description = description
            enum_member.__objclass__ = enum_class
            enum_member.__init__()

            setattr(enum_class, member_name, enum_member)
            enum_class._member_names_.append(member_name)
            enum_class._value2member_map_[code] = enum_member

        return enum_class

    def __get_member__(cls, code):
        if code in cls._value2member_map_:
            return cls._value2member_map_[code]

        enum_member = object.__new__(cls)
        enum_member.name = 'UNDEFINED'
        enum_member.value = code
        enum_member.description = 'Undefined Value'
        enum_member.__objclass__ = cls
        enum_member.__init__()

        cls._value2member_map_[code] = enum_member

        return enum_member

    def __iter__(cls):
        return (getattr(cls, name) for name in cls._member_names_)

    def __len__(cls):
        return len(cls._member_names_)

class Models(metaclass=StatusValueEnum):
    QL500      = 0x304F, "QL-500" # or QL-550, both share the same code
    QL1050     = 0x3050, "QL-1050"
    QL650TD    = 0x3051, "QL-650TD"
    PT9800PCN  = 0x3061, "PT-9800PCN" # TODO check
    PT9700PC   = 0x3062, "PT-9700PC"
    PTH500     = 0x3064, "PT-H500"
    PTE500     = 0x3065, "PT-E500"
    PTE550W    = 0x3066, "PT-E550W"
    PTP700     = 0x3067, "PT-P700"
    PTP750W    = 0x3068, "PT-P750W"
    PTP900W    = 0x306F, "PT-P900W"
    PTP950NW   = 0x3070, "PT-P950NW"
    PTP900     = 0x3071, "PT-P900"

    QL560      = 0x3431, "QL-560"
    QL570      = 0x3432, "QL-570"
    QL580N     = 0x3433, "QL-580N"
    QL1060N    = 0x3434, "QL-1060N"
    QL700      = 0x3435, "QL-700"
    QL710W     = 0x3436, "QL-710W"
    QL720NW    = 0x3437, "QL-720NW"
    QL800      = 0x3438, "QL-800"
    QL810W     = 0x3439, "QL-810W"
    QL820NWB   = 0x3441, "QL-820NWB"
    QL1100     = 0x3443, "QL-1100"
    QL1110NWB  = 0x3444, "QL-1110NWB"
    QL1115NWB  = 0x3445, "QL-1115NWB"
    QL600      = 0x3447, "QL-600"

    TD4000     = 0x3531, "TD-4000" # TODO check
    TD4100N    = 0x3532, "TD-4100N"
    TD2020     = 0x3533, "TD-2020"
    TD2120N    = 0x3535, "TD-2120N"
    TD2130N    = 0x3536, "TD-2130N"
    TD4410D    = 0x3537, "TD-4410D"
    TD4420DN   = 0x3538, "TD-4420DN"
    TD4510D    = 0x3539, "TD-4510D"
    TD4520DN   = 0x3541, "TD-4520DN"
    TD4550DNWB = 0x3542, "TD-4550DNWB"

    RJ4230B    = 0x3743, "RJ-4230B" # TODO check
    RJ4250WB   = 0x3744, "RJ-4250WB"

class BatteryLevels(metaclass=StatusValueEnum):
    # PT series
    FULL              = 0x00, "Full"
    HALF              = 0x01, "Half"
    LOW               = 0x02, "Low"
    NEED_TO_CHARGE    = 0x03, "Need to be charged"
    USING_ADAPTOR     = 0x04, "Using AC adaptor"
    UNKNOWN           = 0xFF, "Unknown"

    # TD/RJ series
    FULL_NC           = 0x20, "Full (AC adapter not connected)"
    HIGH_NC           = 0x21, "High (AC adapter not connected)"
    HALF_NC           = 0x22, "Half (AC adapter not connected)"
    LOW_NC            = 0x23, "Low (AC adapter not connected)"
    NEED_TO_CHARGE_NC = 0x24, "Charging required (AC adapter not connected)"
    FULL_C            = 0x30, "Full (AC adapter connected)"
    HIGH_C            = 0x31, "High (AC adapter connected)"
    HALF_C            = 0x32, "Half (AC adapter connected)"
    LOW_C             = 0x33, "Low (AC adapter connected)"
    NEED_TO_CHARGE_C  = 0x34, "Charging required (AC adapter connected)"
    NO_BATTERY        = 0x37, "No battery Connected"


class AdditionalErrors(metaclass=StatusValueEnum):
    NONE         = 0x00, "No error",
    FLE_TAPE_END = 0x10, "FLe tape end"
    RESOLUTION   = 0x1D, "High-resolution/draft printing error"
    ADAPTOR      = 0x1E, "Adaptor pull/insert error"
    BATTERY      = 0x1F, "Battery error"
    MEDIA        = 0x21, "Incompatible media error"
    SYSTEM       = 0xFF, "System error"


class MediaTypes(metaclass=StatusValueEnum):
    NO_MEDIA         = 0x00, "No media"
    INCOMPATIBLE     = 0xFF, "Incompatible tape"

    # PT series
    LAMINATED        = 0x01, "Laminated tape"
    NON_LAMINATED    = 0x03, "Non-laminated tape"
    FABRIC           = 0x04, "Fabric Tape"
    HEAT_SHRINK_TUBE = 0x11, "Heat-Shrink Tube"
    FLE              = 0x13, "FLe tape"
    FLEXIBLE_ID      = 0x14, "Flexible ID tape"
    SATIN            = 0x15, "Satin tape"

    # QL series
    CONTINUOUS       = 0x0A, "Continuous length tape"
    DIE_CUT          = 0x0B, "Die-cut labels"
    CONTINUOUS2      = 0x4A, "Continuous length tape"
    DIE_CUT2         = 0x4B, "Die-cut labels"


class StatusTypes(metaclass=StatusValueEnum):
    REQUEST       = 0x00, "Reply to status request"
    COMPLETE      = 0x01, "Printing completed"
    ERROR         = 0x02, "Error occurred"
    EXIT_IF       = 0x03, "Exit IF mode"
    TURNED_OFF    = 0x04, "Turned off"
    NOTIFICATION  = 0x05, "Notification"
    PHASE_CHANGE  = 0x06, "Phase change"
    SEND_ADVANCED = 0xF0, "Send advanced data"


class PhaseTypes(metaclass=StatusValueEnum):
    READY    = 0x00, "Waiting to receive"
    PRINTING = 0x01, "Printing state"


class ReadyPhaseNumbers(metaclass=StatusValueEnum):
    EDIT = 0x0000, "Editing state (reception possible)"
    FEED = 0x0001, "Feed"


class PrintingPhaseNumbers(metaclass=StatusValueEnum):
    PRINTING    = 0x0000, "Printing"
    COVER_OPEN  = 0x0014, "Cover open while receiving"


class Notifications(metaclass=StatusValueEnum):
    NOT_AVAILABLE    = 0x00, "Not available"
    COVER_OPEN       = 0x01, "Cover open"
    COVER_CLOSED     = 0x02, "Cover closed"
    COOLING_STARTED  = 0x03, "Cooling (started)"
    COOLING_FINISHED = 0x04, "Cooling (finished)"
    PEELING_WAIT     = 0x05, "Waiting for peeling"
    PEELING_FINISHED = 0x06, "Finished waiting for peeling"
    PAUSED           = 0x07, "Printer paused"
    UNPAUSE          = 0x08, "Finished printer pause"


class TapeColors(metaclass=StatusValueEnum):
    WHITE                   = 0x01, "White"
    OTHER                   = 0x02, "Other"
    CLEAR                   = 0x03, "Clear"
    RED                     = 0x04, "Red"
    BLUE                    = 0x05, "Blue"
    YELLOW                  = 0x06, "Yellow"
    GREEN                   = 0x07, "Green"
    BLACK                   = 0x08, "Black"
    CLEAR_WHITE_TEXT        = 0x09, "Clear(White text)"
    MATTE_WHITE             = 0x20, "Matte White"
    MATTE_CLEAR             = 0x21, "Matte Clear"
    MATTE_SILVER            = 0x22, "Matte Silver"
    SATIN_GOLD              = 0x23, "Satin Gold"
    SATIN_SILVER            = 0x24, "Satin Silver"
    BLUE_D                  = 0x30, "Blue(D)" # TZe-535(12 mm), TZe-545(18 mm), TZe-555(24 mm)
    RED_D                   = 0x31, "Red(D)" # TZe-435(12 mm)
    FLUORESCENT_ORANGE      = 0x40, "Fluorescent Orange"
    FLUORESCENT_YELLOW      = 0x41, "Fluorescent Yellow"
    BERRY_PINK_S            = 0x50, "Berry Pink(S)" # TZe-MQP35
    LIGHT_GRAY_S            = 0x51, "Light Gray(S)" # TZe-MQL35
    LIME_GREEN_S            = 0x52, "Lime Green(S)" # TZe-MQG35
    YELLOW_F                = 0x60, "Yellow(F)"
    PINK_F                  = 0x61, "Pink(F)"
    BLUE_F                  = 0x62, "Blue(F)"
    HEAT_SHRINK_TUBE        = 0x70, "White(Heat-shrink Tube)"
    WHITE_FLEX_ID           = 0x90, "White(Flex. ID)"
    YELLOW_FLEX_ID          = 0x91, "Yellow(Flex. ID)"
    CLEANING                = 0xF0, "Cleaning"
    STENCIL                 = 0xF1, "Stencil"
    INCOMPATIBLE            = 0xFF, "Incompatible"

class TextColors(metaclass=StatusValueEnum):
    WHITE        = 0x01, "White"
    RED          = 0x04, "Red"
    BLUE         = 0x05, "Blue"
    BLACK        = 0x08, "Black"
    GOLD         = 0x0A, "Gold"
    BLUE_F       = 0x62, "Blue(F)"
    CLEANING     = 0xF0, "Cleaning"
    STENCIL      = 0xF1, "Stencil"
    OTHER        = 0x02, "Other"
    INCOMPATIBLE = 0xFF, "Incompatible"


class ErrorInformations(metaclass=StatusValueEnum):
    NO_MEDIA         = 0x0001, "No media"
    END_OF_MEDIA     = 0x0002, "End of media"
    CUTTER_JAM       = 0x0004, "Cutter jam"
    WEAK_BATTERIES   = 0x0008, "Weak batteries"
    IN_USE           = 0x0010, "Printer in use"
    TURNED_OFF       = 0x0020, "Printer turned off"
    HIGH_VOLTAGE     = 0x0040, "High-voltage adapter"
    FAN_MOTOR_ERROR  = 0x0080, "Fan motor error"
    REPLACE_MEDIA    = 0x0100, "Replace media"
    EXP_BUFFER_FULL  = 0x0200, "Expansion buffer full"
    COMM_ERROR       = 0x0400, "Communication error"
    COMM_BUFFER_FULL = 0x0800, "Communication buffer full"
    COVER_OPEN       = 0x1000, "Cover open"
    CANCEL_KEY       = 0x2000, "Cancel key"
    FEED_ERROR       = 0x4000, "Media cannot be fed (or media end detected)"
    SYSTEM_ERROR     = 0x8000, "System error"

STATUS_STRUCT = struct.Struct('>BBBHBBBHBBBBBBBBBBHBBBBLxx')
@attrs
class Status:
    # Offset 0: Always 0x80
    print_head_mark: int = attrib()
    # Offset 1: Size of this struct, always 32 bytes
    size: int = attrib()
    # Offset 2: Always 'B'
    brother_code: int = attrib(converter=chr)
    # Offset 3: Two bytes describing the series and the model
    series_model_code: Models = attrib(converter=Models)
    # Offset 5: Country code, always '0'
    country_code: int = attrib(converter=chr)
    # Offset 6: Battery level (PT-P9 series only)
    battery_level: BatteryLevels = attrib(converter=BatteryLevels)
    # Offset 7: Additional error code (PT-P9 series only)
    extended_error: AdditionalErrors = attrib(converter=AdditionalErrors)
    # Offset 8: Two byte bitmask describing errors
    error_information: int = attrib()
    # Offset 10: Label media width in millimeters
    media_width: int = attrib()
    # Offset 11: Label media type
    media_type: MediaTypes = attrib(converter=MediaTypes)
    # Offset 12: Number of colors, always 0
    number_of_colors: int = attrib()
    # Offset 13: Second byte of the media_length field (TD-4D series only)
    #            PT series documentation calls this fonts but always set to 0
    media_length_msb: int = attrib()
    # Offset 14: Media sensor value (TD-4D series only)
    #            PT series documentation calls this japanese fonts but always
    #            set to 0
    media_sensor_value: int = attrib()
    # Offset 15: TODO
    mode: int = attrib()
    # Offset 16: Density, always 0
    density: int = attrib()
    # Offset 17: Label media length in millimeters
    #            (first byte of two byte value for TD-4D series)
    media_length_lsb: int = attrib()
    # Offset 18: Reason for this status message
    status_type: StatusTypes = attrib(converter=StatusTypes)
    # Offset 19: Printing phase
    phase_type: PhaseTypes = attrib(converter=PhaseTypes)
    # Offset 20: Phase number (PT series only)
    phase_number: int = attrib()
    # Offset 22: Notification code
    notification_number: Notifications = attrib(converter=Notifications)
    # Offset 23: Expansion area (number of bytes), always 0
    expansion_area: int = attrib()
    # Offset 24: Tape color (PT series only)
    tape_color_information: TapeColors = attrib(converter=TapeColors)
    # Offset 25: Text color (PT series only)
    text_color_information: TextColors = attrib(converter=TextColors)
    # Offset 26: Four byte bitmask describing hardware settings (some PT models only)
    hardware_settings: int = attrib()

    @property
    def errors(self):
        errors = []
        for error in ErrorInformations:
            if error.value & self.error_information:
                errors.append(error)

        # only for PT-P9 series
        if self.series_model_code in (0x306F, 0x3070, 0x3071):
            if self.extended_error != AdditionalErrors.NONE:
                errors.append(self.extended_error)

        return errors

    @property
    def media_length(self):
        if self.series_model_code in (0x3537, 0x3538, 0x3539, 0x3541, 0x3542):
            # two byte value only for TD-4D series
            return (self.media_length_msb << 8) & self.media_length_lsb
        else:
            return self.media_length_lsb

    @property
    def phase(self):
        if self.phase_type == PhaseTypes.READY:
            return self.phase_type, ReadyPhaseNumbers(self.phase_number)
        if self.phase_type == PhaseTypes.PRINTING:
            return self.phase_type, PrintingPhaseNumbers(self.phase_number)
        return self.phase_type, None

    @classmethod
    def from_bytes(cls, data):
        return cls(*STATUS_STRUCT.unpack(data))

class PrinterError(RuntimeError):
    def __init__(self, errors):
        super().__init__(*errors)
        self.errors = errors

class PrinterDevice(object):
    def __init__(self, device):
        self.device = device
        backend_type = brother_ql.backends.guess_backend(device)
        self.backend_class = brother_ql.backends.backend_factory(backend_type)['backend_class']
    def __enter__(self):
        self.backend = self.backend_class(self.device)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.backend.dispose()
        self.backend = None

    def status(self):
        self.backend.write(b'\x1B\x69\x53')
        for i in range(10):
            data = self.backend.read()
            if data:
                break
            time.sleep(.02)
        else:
            raise TimeoutError("Failed to read data from printer")
        return Status.from_bytes(data)

    def info(self):
        status = self.status()

        if status.errors:
            raise PrinterError(status.errors)

        if status.media_type == MediaTypes.NO_MEDIA:
            label_ = None
        else:
            for label in brother_ql.labels.LabelsManager().iter_elements():
                if label.tape_size == (status.media_width, status.media_length):
                    label_ = label
                    break
            else: # no match
                raise RuntimeError("Unknown label type: {}mm x {}mm ({})".format(
                    status.media_width,
                    status.media_length,
                    status.media_type.description,
                    ))

        for model in brother_ql.models.ModelsManager().iter_elements():
            if model.identifier == status.series_model_code.description:
                model_ = model
                break
        else: # no match
            raise RuntimeError("Unknown model: {}".format(
                status.series_model_code.description,
                ))

        return (model_, label_)

    def print(self, qlr):
        self.backend.write(qlr.data)

        # Print request is answered three times:
        #   1. phase changed to printing
        #   2. printing complete
        #   3. phase changed to ready
        for expected_status in (StatusTypes.PHASE_CHANGE,
                                StatusTypes.COMPLETE,
                                StatusTypes.PHASE_CHANGE):
            for i in range(250):
                data = self.backend.read()
                if data:
                    break
                time.sleep(.02)
            else:
                raise TimeoutError("Failed to read data from printer")

            status = Status.from_bytes(data)

            if status.errors:
                raise PrinterError(status.errors)

            if status.status_type != expected_status:
                raise RuntimeError("Expected status \"{}\" but got \"{}\"".format(
                    expected_status.description,
                    status.status_type.description,
                    ))
