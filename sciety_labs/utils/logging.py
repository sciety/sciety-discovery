from contextlib import contextmanager
import logging
import logging.handlers
import queue
from typing import Iterator, List, Optional, Sequence


LOGGER = logging.getLogger(__name__)


@contextmanager
def threaded_logging(
    loggers: Optional[Sequence[logging.Logger]] = None
) -> Iterator[logging.handlers.QueueListener]:
    queue_listener: Optional[logging.handlers.QueueListener] = None
    if loggers is None:
        loggers = [logging.root]
    original_handlers_list = [logger.handlers for logger in loggers]
    try:
        logging_queue = queue.Queue(-1)
        queue_handlers: List[logging.handlers.QueueHandler] = []
        for logger in loggers:
            stream_handlers = [
                handler
                for handler in logger.handlers
                if isinstance(handler, logging.StreamHandler)
            ]
            if not stream_handlers:
                pass
            LOGGER.info('Using queue handler instead of stream handlers: %r', stream_handlers)
            queue_handler = logging.handlers.QueueHandler(logging_queue)
            logger.handlers = (
                [
                    handler for handler in logger.handlers
                    if not isinstance(handler, logging.StreamHandler)
                ]
                + [queue_handler]
            )
            queue_handlers.append(queue_handler)
        queue_listener = logging.handlers.QueueListener(
            logging_queue,
            *queue_handlers
        )
        queue_listener.start()
        yield queue_listener
    finally:
        if queue_listener is not None:
            queue_listener.stop()
        for logger, original_handlers in zip(loggers, original_handlers_list):
            logger.handlers = original_handlers
