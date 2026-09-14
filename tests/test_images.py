from medbot.extract import Block, Section
from medbot.images import MIN_IMAGE_BYTES, download_all_images, download_image


def test_returns_bytes_when_large_enough():
    data = b"x" * (MIN_IMAGE_BYTES + 1)
    assert download_image("https://x.test/a.jpg", fetcher=lambda url: data) == data


def test_rejects_image_smaller_than_threshold():
    # trafilatura xoa mat width/height nen day la lop loc thu hai: anh
    # thuc su tai ve qua nho gan nhu chac chan la icon/pixel theo doi
    data = b"x" * (MIN_IMAGE_BYTES - 1)
    assert download_image("https://x.test/tiny.gif", fetcher=lambda url: data) is None


def test_returns_none_when_fetcher_raises():
    def boom(url):
        raise ConnectionError("mạng lỗi")
    assert download_image("https://x.test/a.jpg", fetcher=boom) is None


def test_download_all_images_fills_image_bytes_in_place():
    good = b"x" * (MIN_IMAGE_BYTES + 1)
    section = Section(heading="H", blocks=[Block(kind="image", src="https://x.test/a.jpg")])
    download_all_images([section], fetcher=lambda url: good)
    assert section.blocks[0].image_bytes == good


def test_download_all_images_leaves_none_on_failure_without_crashing():
    section = Section(heading="H", blocks=[Block(kind="image", src="https://x.test/broken.jpg")])
    download_all_images([section], fetcher=lambda url: (_ for _ in ()).throw(ConnectionError()))
    assert section.blocks[0].image_bytes is None


def test_download_all_images_skips_non_image_blocks():
    def boom(url):
        raise AssertionError("Không được gọi fetcher cho block không phải ảnh")

    section = Section(heading="H", blocks=[Block(kind="p", text="không phải ảnh")])
    download_all_images([section], fetcher=boom)
    assert section.blocks[0].image_bytes is None
