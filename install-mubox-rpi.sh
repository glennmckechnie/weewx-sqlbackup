#!/bin/bash

#BASE_URL=http://mirror.voyage.hk/download/voyage-mubox
BASE_URL=http://192.168.0.100/voyage-mubox
URL_MUBOX=$BASE_URL/voyage-mubox-rpi-current.tar.xz
URL_RPI_FW="https://github.com/Hexxeh/rpi-firmware/"


if [ -z "$1" ] ; then
	echo "Usage: $(basename $0) <install flash dev>"
	exit 1
fi

if [ ! -b "$1" ] ; then
	echo "$1 is not a disk device"
	exit 1
fi 

card=$1
mntpt=/tmp/cf
mntpt1=/tmp/cf1

if [ ! -d "$mntpt" ] ; then mkdir -p $mntpt; fi
if [ ! -d "$mntpt1" ] ; then mkdir -p $mntpt1; fi

checkCmd()
{
	CMD=`which $1`
	if [ -z "$CMD" ] ; then
		echo "Command $1 not found!  Please install it first."
		exit 1
	fi
}

checkCaCerts()
{
	DIR=/etc/ssl/certs/
	if [ $(ls $DIR |wc -l) -eq 0 ] ; then 
		echo "No certs in $DIR.  Please install ca-certificates package first."
		exit 1
	fi
}


formatCard()
{
# 1 partition , 1 ext4, no journal
dd if=/dev/zero of=$card bs=512 count=1
[ -b $card ] && fdisk -u $card <<EOF
o
n
p
1

+64M
t
c
n
p
2


w

EOF

echo "sleep 5"
sleep 5
echo "syncing"
sync
echo "sleep 5"
sleep 5


# create ext4 filesystem, no mount check and assign volume label
mkfs.vfat ${card}1
mkfs.ext4 ${card}2
tune2fs -i 0 -c 0 ${card}2 -L voyage-mubox -O ^has_journal
#tune2fs -i 0 -c 0 ${card}2 

echo "sleep 5"
sleep 5
echo "syncing again"
sync
echo "sleep 5"
sleep 5

fdisk -l ${card}

echo "disk partioned and formatted - check if valid"
wait

}

#
# Install Boot
#  $1 - RPi Firmware URL
#
installBoot()
{
	REPO_API="https://api.github.com/repos/Hexxeh/rpi-firmware/git/refs/heads/master"
	GITREV=$(curl -s ${REPO_API} | awk '{ if ($1 == "\"sha\":") { print substr($2, 2, 40) } }')
	FW_REV=${FW_REV:-${GITREV}}

	mount ${card}2 ${mntpt}
	curl -L "$1"/tarball/${FW_REV} | tar -xzf - -C ${mntpt}/boot/ --strip-components=1
	sync
	
	umount ${mntpt}
	sync
}

#
# Install Root 
#  $1 - install tarball URL
#
installRoot()
{
	mount ${card}2 ${mntpt}
	curl $1 | tar --numeric-owner -Jxf - -C ${mntpt}
	umount ${mntpt}
	sync
}

postInstall()
{
	## boot partition
        mount ${card}1 ${mntpt1}
	## rootfs partition
        mount ${card}2 ${mntpt}

	## cmdline.txt
	echo "dwc_otg.lpm_enable=0 console=ttyAMA0,115200 kgdboc=ttyAMA0,115200 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 elevator=noop rootwait" > ${mntpt1}/cmdline.txt
	sync

	## firmware
	cp "${mntpt}/boot/"*.elf "${mntpt1}/"
	cp "${mntpt}/boot/"*.bin "${mntpt1}/"
	cp "${mntpt}/boot/"*.dat "${mntpt1}/"
	cp "${mntpt}/boot/"*.img "${mntpt1}/"
	cp "${mntpt}/boot/"*.dtb "${mntpt1}/"
	mkdir -p ${mntpt1}/overlays
	cp "${mntpt}/boot/overlays/"*.dtb "${mntpt1}/overlays"

	if [ -f "${mntpt}/boot/"Module.symvers ]; then
		cp "${mntpt}/boot/"Module.symvers "${mntpt1}/"
	fi
	if [ -f "${mntpt}/boot/"git_hash ]; then
		cp "${mntpt}/boot/"git_hash "${mntpt1}/"
	fi

	## update modules
	cp -R "${mntpt}/boot/modules/"* "${mntpt}/lib/modules/"
	find "${mntpt}/boot/modules" -mindepth 1 -maxdepth 1 -type d | while read DIR; do
		BASEDIR=$(basename "${DIR}")
		echo " *** depmod ${BASEDIR}"
		depmod -b "${mntpt}" -a "${BASEDIR}"
	done

	## copy video core
	cp -R "${mntpt}/boot/vc/hardfp/"* "${mntpt}/"

	## inittab
	sed -i -e "s/ttyS0/ttyAMA0/" ${mntpt}/etc/inittab
	#sed -i -e "/^options.*snd-usb-audio/s/^/#/" ${mntpt}/etc/modprobe.d/alsa-base.conf

	## asound.conf
	echo "
pcm.!default  {
    type hw
    card 0
}
ctl.!default {
    type hw
    card 0
}
" >> ${mntpt}/etc/asound.conf 

	## alsa-base.conf
	sed -i -e "s/^options snd-usb/#options snd-usb/" ${mntpt}/etc/modprobe.d/alsa-base.conf

	## mpd.conf  - change mixer_contrl for DAC+
	#sed -i -e "/device.*\"hw/a mixer_control        \"Digital\"" ${mntpt}/etc/mpd.conf

	## config.txt
	cp "${mntpt}/boot/"config.txt "${mntpt1}/"
	echo "
#device_tree_overlay=overlays/hifiberry-dacplus-overlay.dtb
dtoverlay=hifiberry-dacplus
" >> ${mntpt1}/config.txt 


	## rpi-update
	curl -L https://raw.github.com/Hexxeh/rpi-update/master/rpi-update -o ${mntpt}/usr/bin/rpi-update
	chmod +x ${mntpt}/usr/bin/rpi-update

	## copy boot
	mkdir ${mntpt}/boot.bak
	mv ${mntpt}/boot/* ${mntpt}/boot.bak/

	## mount boot partition
	echo "
/dev/mmcblk0p1 /boot vfat defaults 0 0
" >> ${mntpt}/etc/fstab

	## finished, sync and unmount
	sync
        umount ${mntpt1}
        umount ${mntpt}
        sync
}


checkCmd dd
checkCmd tar
checkCmd xz
checkCmd mount
checkCmd umount
checkCmd sync
checkCmd fdisk
checkCmd curl
checkCmd mkfs.ext4
checkCmd mkfs.vfat
checkCmd tune2fs
checkCmd find
checkCmd gunzip
checkCaCerts

formatCard
echo " fdisk & Formatting is done"
wait
installRoot $URL_MUBOX
echo "install of root is done"
wait
installBoot $URL_RPI_FW
echo " install Boot"
wait
postInstall

sync
sleep 5
echo ""
echo "Voyage MuBox for RaspBerry Pi installed!"

