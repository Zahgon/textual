"""
An encoding / decoding format suitable for serializing data structures to binary.

This is based on https://en.wikipedia.org/wiki/Bencode with some extensions.

The following data types may be encoded:

- None
- int
- bool
- bytes
- str
- list
- tuple
- dict

"""

from __future__ import annotations

from typing import Any, Callable


class DecodeError(Exception):
    """A problem decoding data."""


def dump(data: object) -> bytes:
    """Encodes a data structure into bytes.

    Args:
        data: Data structure

    Returns:
        A byte string encoding the data.
    """

    def encode_none(_datum: None) -> bytes:
        """
        Encodes a None value.

        Args:
            datum: Always None.

        Returns:
            None encoded.
        """
        pass

    def encode_bool(datum: bool) -> bytes:
        """
        Encode a boolean value.

        Args:
            datum: The boolean value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    def encode_int(datum: int) -> bytes:
        """
        Encode an integer value.

        Args:
            datum: The integer value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    def encode_bytes(datum: bytes) -> bytes:
        """
        Encode a bytes value.

        Args:
            datum: The bytes value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    def encode_string(datum: str) -> bytes:
        """
        Encode a string value.

        Args:
            datum: The string value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    def encode_list(datum: list) -> bytes:
        """
        Encode a list value.

        Args:
            datum: The list value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    def encode_tuple(datum: tuple) -> bytes:
        """
        Encode a tuple value.

        Args:
            datum: The tuple value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    def encode_dict(datum: dict) -> bytes:
        """
        Encode a dictionary value.

        Args:
            datum: The dictionary value to encode.

        Returns:
            The encoded bytes.
        """
        pass

    ENCODERS: dict[type, Callable[[Any], Any]] = {
        type(None): encode_none,
        bool: encode_bool,
        int: encode_int,
        bytes: encode_bytes,
        str: encode_string,
        list: encode_list,
        tuple: encode_tuple,
        dict: encode_dict,
    }

    def encode(datum: object) -> bytes:
        """Recursively encode data.

        Args:
            datum: Data suitable for encoding.

        Raises:
            TypeError: If `datum` is not one of the supported types.

        Returns:
            Encoded data bytes.
        """
        try:
            decoder = ENCODERS[type(datum)]
        except KeyError:
            raise TypeError("Can't encode {datum!r}") from None
        return decoder(datum)

    return encode(data)


def load(encoded: bytes) -> object:
    """Load an encoded data structure from bytes.

    Args:
        encoded: Encoded data in bytes.

    Raises:
        DecodeError: If an error was encountered decoding the string.

    Returns:
        Decoded data.
    """
    if not isinstance(encoded, bytes):
        raise TypeError("must be bytes")
    max_position = len(encoded)
    position = 0

    def get_byte() -> bytes:
        """Get an encoded byte and advance position.

        Raises:
            DecodeError: If the end of the data was reached

        Returns:
            A bytes object with a single byte.
        """
        nonlocal position
        if position >= max_position:
            raise DecodeError("More data expected")
        character = encoded[position : position + 1]
        position += 1
        return character

    def peek_byte() -> bytes:
        """Get the byte at the current position, but don't advance position.

        Returns:
            A bytes object with a single byte.
        """
        return encoded[position : position + 1]

    def get_bytes(size: int) -> bytes:
        """Get a number of bytes of encode data.

        Args:
            size: Number of bytes to retrieve.

        Raises:
            DecodeError: If there aren't enough bytes.

        Returns:
            A bytes object.
        """
        nonlocal position
        bytes_data = encoded[position : position + size]
        if len(bytes_data) != size:
            raise DecodeError(b"Missing bytes in {bytes_data!r}")
        position += size
        return bytes_data

    def decode_int() -> int:
        """Decode an int from the encoded data.

        Returns:
            An integer.
        """
        pass

    def decode_bytes(size_bytes: bytes) -> bytes:
        """Decode a bytes string from the encoded data.

        Returns:
            A bytes object.
        """
        while (byte := get_byte()) != b":":
            size_bytes += byte
        bytes_string = get_bytes(int(size_bytes))
        return bytes_string

    def decode_string() -> str:
        """Decode a (utf-8 encoded) string from the encoded data.

        Returns:
            A string.
        """
        pass

    def decode_list() -> list[object]:
        """Decode a list.

        Returns:
            A list of data.
        """
        pass

    def decode_tuple() -> tuple[object, ...]:
        """Decode a tuple.

        Returns:
            A tuple of decoded data.
        """
        pass

    def decode_dict() -> dict[object, object]:
        """Decode a dict.

        Returns:
            A dict of decoded data.
        """
        pass

    DECODERS = {
        b"i": decode_int,
        b"s": decode_string,
        b"l": decode_list,
        b"t": decode_tuple,
        b"d": decode_dict,
        b"T": lambda: True,
        b"F": lambda: False,
        b"N": lambda: None,
    }

    def decode() -> object:
        """Recursively decode data.

        Returns:
            Decoded data.
        """
        decoder = DECODERS.get(initial := get_byte(), None)
        if decoder is None:
            return decode_bytes(initial)
        return decoder()

    return decode()
