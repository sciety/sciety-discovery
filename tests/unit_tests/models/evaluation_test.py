from sciety_labs.models.evaluation import ScietyEventEvaluationStatsModel


ARTICLE_ID_1 = 'doi:10.1234/doi_1'
ARTICLE_ID_2 = 'doi:10.1234/doi_2'

EVALUATION_LOCATOR_1 = 'test:evaluation_1'
EVALUATION_LOCATOR_2 = 'test:evaluation_2'
EVALUATION_LOCATOR_3 = 'test:evaluation_3'


EVALUATION_RECORDED_EVENT_1 = {
    'event_name': 'EvaluationRecorded',
    'article_id': ARTICLE_ID_1,
    'evaluation_locator': EVALUATION_LOCATOR_1
}


class TestScietyEventEvaluationStatsModel:
    def test_should_return_zero_evaluation_count_for_no_events(self):
        model = ScietyEventEvaluationStatsModel([])
        assert model.get_evaluation_count_by_article_id(ARTICLE_ID_1) == 0

    def test_should_ignore_evaluations_with_different_article_id(self):
        model = ScietyEventEvaluationStatsModel([{
            **EVALUATION_RECORDED_EVENT_1,
            'article_id': ARTICLE_ID_2
        }])
        assert model.get_evaluation_count_by_article_id(ARTICLE_ID_1) == 0

    def test_should_return_count_of_evaluations_with_same_article_id(self):
        model = ScietyEventEvaluationStatsModel([{
            **EVALUATION_RECORDED_EVENT_1,
            'article_id': ARTICLE_ID_1,
            'evaluation_locator': EVALUATION_LOCATOR_1
        }, {
            **EVALUATION_RECORDED_EVENT_1,
            'article_id': ARTICLE_ID_1,
            'evaluation_locator': EVALUATION_LOCATOR_2
        }])
        assert model.get_evaluation_count_by_article_id(ARTICLE_ID_1) == 2

    def test_should_match_article_id_ignoring_case(self):
        model = ScietyEventEvaluationStatsModel([{
            **EVALUATION_RECORDED_EVENT_1,
            'article_id': 'doi:10.1234/Doi_1',
            'evaluation_locator': EVALUATION_LOCATOR_1
        }, {
            **EVALUATION_RECORDED_EVENT_1,
            'article_id': 'doi:10.1234/dOi_1',
            'evaluation_locator': EVALUATION_LOCATOR_2
        }])
        assert model.get_evaluation_count_by_article_id('doi:10.1234/doI_1') == 2
