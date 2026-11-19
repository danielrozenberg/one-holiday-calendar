from holidaycal import config_pb2


def test_round_trip():
    config = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA", subdivisions=["ON"]),
            config_pb2.Source(religion="christian"),
        ],
        title_style=config_pb2.TITLE_STYLE_PREFIX_CODES,
    )

    parsed = config_pb2.Config.FromString(config.SerializeToString())

    assert parsed == config
    assert parsed.sources[1].WhichOneof("kind") == "religion"
