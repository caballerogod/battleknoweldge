import pytest
from app.trivia_media import validate_mixed


def clue(answer='eau de parfum'):
    return dict(topic_index=0,price=200,kind='choice',image_id='',answer=answer,
                aliases=['Одеколон'],options=['Eau de Parfum','Одеколон','Духи','Туалетная вода'])


@pytest.mark.parametrize('answer',['eau de parfum',' EAU DE PARFUM ','Eau de Parfum'])
def test_reference_uses_actual_option_text(answer):
    row=clue(answer)
    validate_mixed([row],expected_count=1)
    assert row['answer']=='Eau de Parfum'
    assert row['answer']!=row['aliases'][0]


@pytest.mark.parametrize('answer',['Eau de Parfum!','Неизвестный ответ'])
def test_substantively_different_reference_still_rejected(answer):
    with pytest.raises(ValueError):
        validate_mixed([clue(answer)],expected_count=1)


def test_equivalent_options_still_rejected():
    row=clue();row['options'][-1]=' eau de parfum '
    with pytest.raises(ValueError):
        validate_mixed([row],expected_count=1)
