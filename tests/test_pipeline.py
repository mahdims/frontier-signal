from frontier_signal.pipeline import bounded_content


def test_bounded_content_strips_cached_html_and_limits_length():
    content = '<div class="article"><p>Useful AI result</p><img src="noise"></div>'

    assert bounded_content(content, 12) == "Useful AI re"
