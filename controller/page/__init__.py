from . import view, api, ocr

views = [
    view.PageBrowseHandler, view.PageViewHandler,
    view.TaskCutHandler, view.CutEditHandler,
    view.TaskTextProofHandler, view.TaskTextReviewHandler, view.TextEditHandler,
    view.CharEditHandler,
]

handlers = [
    ocr.FetchTasksApi, ocr.SubmitTasksApi, ocr.ConfirmFetchTasksApi,
    api.TaskPublishApi, api.TaskCutApi, api.CutEditApi,
    api.TaskTextSelectApi, api.TaskTextProofApi, api.TaskTextReviewApi, api.TaskTextHardApi,
    api.TextEditApi, api.TextNeighborApi, api.TextsDiffApi, api.DetectWideCharsApi,
]

modules = {'TextArea': view.TextArea}
