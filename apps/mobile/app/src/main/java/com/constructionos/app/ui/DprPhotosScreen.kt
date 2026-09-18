package com.constructionos.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.constructionos.app.core.authorization.hasProjectPermission
import com.constructionos.app.core.database.DprPhotoEntity
import com.constructionos.app.core.database.DprPhotoState
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprPhotoRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun DprPhotosScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    dprRepository: DprRepository,
    photoRepository: DprPhotoRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val appContext = LocalContext.current
    val reports by remember(project.id) {
        dprRepository.observeProjectReports(project.id)
    }.collectAsState(initial = emptyList())
    var selectedReportId by rememberSaveable(project.id) { mutableStateOf<String?>(null) }
    var caption by rememberSaveable(project.id, selectedReportId) { mutableStateOf("") }
    var photosEnabled by remember(project.id) { mutableStateOf(true) }
    var message by remember(project.id) { mutableStateOf<String?>(null) }
    var refreshing by remember(project.id) { mutableStateOf(false) }
    var pendingCaptureUri by remember { mutableStateOf<Uri?>(null) }
    var pendingCapturePath by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(project.id, context.configurationRevision) {
        runCatching { dprRepository.enabledSections(project.id) }
            .onSuccess { photosEnabled = "photos" in it }
    }

    LaunchedEffect(reports) {
        val selected = selectedReportId
        if (selected == null || reports.none { it.id == selected }) {
            selectedReportId = reports.firstOrNull { it.status == DprRepository.STATUS_DRAFT }?.id
                ?: reports.firstOrNull()?.id
        }
    }

    val selectedReport = reports.firstOrNull { it.id == selectedReportId }
    val photosFlow = remember(selectedReportId) {
        selectedReportId?.let(photoRepository::observePhotos) ?: flowOf(emptyList())
    }
    val photos by photosFlow.collectAsState(initial = emptyList())
    val canUpdate = context.hasProjectPermission(project.id, "field.daily_report.update")
    val canUpload = context.hasProjectPermission(project.id, "files.file.upload")
    val canAddPhoto = photosEnabled && canUpdate && canUpload &&
        selectedReport?.status == DprRepository.STATUS_DRAFT &&
        selectedReport.syncState != DprSyncState.NEEDS_ATTENTION

    fun refreshSelected() {
        val report = selectedReport ?: return
        if (report.serverId == null) return
        scope.launch {
            refreshing = true
            message = null
            runCatching { photoRepository.refreshReport(report.id) }
                .onFailure {
                    message = "Could not refresh server photos. Saved device photos are still shown."
                }
            refreshing = false
        }
    }

    fun stagePhoto(uri: Uri, captureFile: File? = null) {
        val report = selectedReport
        if (report == null) {
            captureFile?.delete()
            return
        }
        scope.launch {
            message = null
            runCatching {
                photoRepository.stageGalleryPhoto(
                    reportId = report.id,
                    sourceUri = uri,
                    caption = caption,
                )
            }.onSuccess {
                caption = ""
            }.onFailure { error ->
                message = error.message ?: "The photo could not be saved on this device."
            }
            captureFile?.delete()
        }
    }

    LaunchedEffect(selectedReport?.id, selectedReport?.revision, selectedReport?.serverId) {
        if (selectedReport?.serverId != null) {
            runCatching { photoRepository.refreshReport(selectedReport.id) }
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) stagePhoto(uri)
    }

    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val uri = pendingCaptureUri
        val file = pendingCapturePath?.let(::File)
        pendingCaptureUri = null
        pendingCapturePath = null
        if (success && uri != null && file?.isFile == true && file.length() > 0) {
            stagePhoto(uri, file)
        } else {
            file?.delete()
            if (success) message = "The camera did not return a usable photo."
        }
    }

    fun launchCameraCapture() {
        runCatching {
            val directory = File(appContext.cacheDir, "dpr-capture")
            check(directory.mkdirs() || directory.isDirectory) { "Could not prepare the camera." }
            val file = File(directory, "dpr-${UUID.randomUUID()}.jpg")
            val uri = FileProvider.getUriForFile(
                appContext,
                "${appContext.packageName}.fileprovider",
                file,
            )
            pendingCaptureUri = uri
            pendingCapturePath = file.absolutePath
            cameraLauncher.launch(uri)
        }.onFailure { error ->
            pendingCapturePath?.let(::File)?.delete()
            pendingCaptureUri = null
            pendingCapturePath = null
            message = error.message ?: "No camera app is available on this device."
        }
    }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            launchCameraCapture()
        } else {
            message = "Camera permission is needed only when you choose Take photo. You can still choose an existing image."
        }
    }

    fun requestCameraCapture() {
        if (
            ContextCompat.checkSelfPermission(
                appContext,
                Manifest.permission.CAMERA,
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            launchCameraCapture()
        } else {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Rounded.ArrowBack, contentDescription = "Back")
            }
            Column(modifier = Modifier.weight(1f)) {
                Text("DPR photos", style = MaterialTheme.typography.headlineSmall)
                Text(
                    project.name,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(
                onClick = { refreshSelected() },
                enabled = selectedReport?.serverId != null && !refreshing,
            ) {
                Icon(Icons.Rounded.Refresh, contentDescription = "Refresh")
            }
        }

        if (!photosEnabled) {
            Surface(
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            ) {
                Text(
                    "Photos are disabled by this project's Daily Report configuration.",
                    modifier = Modifier.padding(16.dp),
                )
            }
            return@Column
        }

        message?.let {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(10.dp))
            }
        }

        if (reports.isEmpty()) {
            Text(
                "Start a Daily Report before adding site photos.",
                modifier = Modifier.padding(top = 18.dp),
            )
            return@Column
        }

        Text(
            "Report",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(top = 12.dp),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            reports.take(MAX_REPORT_CHOICES).forEach { report ->
                FilterChip(
                    selected = report.id == selectedReportId,
                    onClick = {
                        selectedReportId = report.id
                        message = null
                    },
                    label = {
                        Text("${reportDateLabel(report)} • ${report.status.replace('_', ' ')}")
                    },
                )
            }
        }

        val report = selectedReport ?: return@Column

        if (canAddPhoto) {
            Card(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                shape = MaterialTheme.shapes.extraLarge,
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    OutlinedTextField(
                        value = caption,
                        onValueChange = { if (it.length <= 1000) caption = it },
                        label = { Text("Caption (optional)") },
                        minLines = 2,
                        maxLines = 3,
                        shape = MaterialTheme.shapes.large,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Button(
                            onClick = { requestCameraCapture() },
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(Icons.Rounded.CameraAlt, contentDescription = null)
                            Text("Take photo", modifier = Modifier.padding(start = 7.dp))
                        }
                        OutlinedButton(
                            onClick = { picker.launch("image/*") },
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(Icons.Rounded.PhotoLibrary, contentDescription = null)
                            Text("Choose", modifier = Modifier.padding(start = 7.dp))
                        }
                    }
                    Text(
                        "Saved privately first; resumable upload continues from the server-confirmed byte after interruptions.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 9.dp),
                    )
                }
            }
        } else {
            val reason = when {
                report.status != DprRepository.STATUS_DRAFT ->
                    "Photos are read-only after the report leaves Draft."
                report.syncState == DprSyncState.NEEDS_ATTENTION ->
                    "Resolve the Daily Report sync conflict before adding more photos."
                !canUpdate || !canUpload ->
                    "Your current project permissions do not allow photo upload."
                else -> "Photo upload is not available for this report."
            }
            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                Text(reason, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(11.dp))
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Photos", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
            CosStatusPill("${photos.size}")
        }

        if (photos.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(top = 22.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(
                    Icons.Rounded.Image,
                    contentDescription = null,
                    modifier = Modifier.size(40.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "No photos attached yet",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 9.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                items(photos, key = { it.clientPhotoId }) { photo ->
                    DprPhotoCard(
                        photo = photo,
                        report = report,
                        onRetry = {
                            scope.launch {
                                message = null
                                runCatching { photoRepository.retryPhoto(photo.clientPhotoId) }
                                    .onFailure { message = it.message ?: "Photo could not be retried." }
                            }
                        },
                        onDiscard = {
                            scope.launch {
                                message = null
                                runCatching { photoRepository.discardLocalPhoto(photo.clientPhotoId) }
                                    .onFailure { message = it.message ?: "Photo could not be cancelled." }
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun DprPhotoCard(
    photo: DprPhotoEntity,
    report: DprReportEntity,
    onRetry: () -> Unit,
    onDiscard: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            DprPhotoThumbnail(photo.thumbnailPath)
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        photo.filename,
                        style = MaterialTheme.typography.titleSmall,
                        modifier = Modifier.weight(1f),
                        maxLines = 2,
                    )
                    CosStatusPill(
                        dprPhotoStateLabel(photo.state),
                        tone = photoStateTone(photo.state),
                    )
                }
                photo.caption?.takeIf { it.isNotBlank() }?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 5.dp),
                    )
                }
                if (
                    photo.sizeBytes > 0 &&
                    photo.uploadedBytes > 0 &&
                    photo.state in setOf(DprPhotoState.UPLOADING, DprPhotoState.WAITING_FOR_NETWORK)
                ) {
                    val progress = photo.uploadedBytes.coerceAtMost(photo.sizeBytes).toFloat() / photo.sizeBytes.toFloat()
                    LinearProgressIndicator(
                        progress = { progress },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    )
                    Text(
                        "${(progress * 100).toInt()}% • ${formatBytes(photo.uploadedBytes)} of ${formatBytes(photo.sizeBytes)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 3.dp),
                    )
                }
                if (photo.state == DprPhotoState.CANCEL_REQUESTED) {
                    Text(
                        "Cancellation is saved locally and will be confirmed with the server when connectivity returns.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 5.dp),
                    )
                }
                if (photo.state == DprPhotoState.NEEDS_ATTENTION) {
                    Text(
                        if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
                            "Reconcile the Daily Report before retrying this photo."
                        } else {
                            "Upload needs attention${photo.errorCode?.let { " • $it" }.orEmpty()}."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(top = 5.dp),
                    )
                    TextButton(
                        onClick = onRetry,
                        enabled = report.syncState != DprSyncState.NEEDS_ATTENTION,
                    ) { Text("Retry") }
                }
                val canDiscard = photo.serverAssetId == null &&
                    photo.state != DprPhotoState.CANCEL_REQUESTED
                if (canDiscard) {
                    TextButton(onClick = onDiscard) {
                        Text(if (photo.uploadSessionId == null) "Discard" else "Cancel upload")
                    }
                }
            }
        }
    }
}

@Composable
private fun DprPhotoThumbnail(path: String?) {
    val bitmap by produceState<ImageBitmap?>(initialValue = null, key1 = path) {
        value = withContext(Dispatchers.IO) {
            path?.takeIf { File(it).isFile }
                ?.let(BitmapFactory::decodeFile)
                ?.asImageBitmap()
        }
    }
    val image = bitmap
    if (image != null) {
        Image(
            bitmap = image,
            contentDescription = "DPR photo thumbnail",
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .size(104.dp)
                .clip(MaterialTheme.shapes.large),
        )
    } else {
        Surface(
            modifier = Modifier.size(104.dp),
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surface,
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(Icons.Rounded.Image, contentDescription = "Photo")
            }
        }
    }
}

private fun photoStateTone(state: String): CosStatusTone = when (state) {
    DprPhotoState.SYNCED -> CosStatusTone.SUCCESS
    DprPhotoState.UPLOADING -> CosStatusTone.PRIMARY
    DprPhotoState.WAITING_FOR_NETWORK,
    DprPhotoState.CANCEL_REQUESTED -> CosStatusTone.WARNING
    DprPhotoState.NEEDS_ATTENTION -> CosStatusTone.ERROR
    else -> CosStatusTone.NEUTRAL
}

private fun reportDateLabel(report: DprReportEntity): String = runCatching {
    LocalDate.parse(report.reportDate).format(DateTimeFormatter.ofPattern("d MMM yyyy"))
}.getOrDefault(report.reportDate)

private fun dprPhotoStateLabel(state: String): String = when (state) {
    DprPhotoState.SAVED_ON_DEVICE -> "Saved"
    DprPhotoState.WAITING_FOR_NETWORK -> "Offline"
    DprPhotoState.UPLOADING -> "Uploading"
    DprPhotoState.CANCEL_REQUESTED -> "Cancelling"
    DprPhotoState.SYNCED -> "Synced"
    DprPhotoState.NEEDS_ATTENTION -> "Attention"
    else -> state.replace('_', ' ')
}

private fun formatBytes(bytes: Long): String = when {
    bytes >= 1024L * 1024L -> "%.1f MB".format(bytes.toDouble() / (1024.0 * 1024.0))
    bytes >= 1024L -> "%.1f KB".format(bytes.toDouble() / 1024.0)
    else -> "$bytes B"
}

private const val MAX_REPORT_CHOICES = 8
