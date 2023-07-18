from PySide6.QtCore import QRunnable, Slot, Signal, QObject


class Worker(QRunnable):
    # Custom signals only work on QObjects (QRunnable is not derived from QObject)
    class WorkerSignals(QObject):
        """
        Defines the signals available from a running worker thread. Supported signals are:

        `finished`
            Emitted when the worker is done (either normally or because of an error).

        `error(Exception)`
            Emitted in case of an error. Data is the occurred exception.

        `result(object)`
            Emitted when the worker successfully finished. Data is the return value of the function that was run.

        `progress(int)`
            Emitted when progress changes. Data is the integer indicating the progress in percent (%).
        """
        finished = Signal()
        error = Signal(Exception)
        result = Signal(object)
        progress = Signal(int)
    
    def __init__(self, func, use_progress_callback: bool = True, *args, **kwargs):
        """
        Creates a new worker thread that runs the specified function. The `finished`, `error`, `result` and `progress`
        attributes can be used to set up the various callbacks that should be run (see `workers.Worker.WorkerSignals`).

        :param func: The function to run on this worker thread. The specified `args` and `kwargs` will be passed to this
            function when called by the worker.
        :param use_progress_callback: If True, then an additional keyword argument "progress_callback", which contains
            the `WorkerSignals.progress` signal, will be passed to the function in order for the function to emit
            progress feedback. In this case, `kwargs` must not already contain "progress_callback".
        :param args: Arguments to pass to the function.
        :param kwargs: Keyword arguments to pass to the function. Must not contain "progress_callback" if
            `use_progress_callback` is set to True.
        """
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        # Must be an attribute, since otherwise, the instance is deleted, and we get an error (RuntimeError: Signal
        # source has been deleted). Could also make "signals" public and then set the callbacks via, e.g.,
        # "worker.signals.error", but "worker.error" is just more convenient
        self._signals = Worker.WorkerSignals()
        self.finished = self._signals.finished
        self.error = self._signals.error
        self.result = self._signals.result
        self.progress = self._signals.progress
        if use_progress_callback:
            if "progress_callback" in self.kwargs:
                raise ValueError("kwargs must not contain 'progress_callback' when use_progress_callback=True")
            self.kwargs["progress_callback"] = self._signals.progress
    
    @Slot()
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.error.emit(e)
        else:
            self.result.emit(result)
        finally:
            self.finished.emit()
