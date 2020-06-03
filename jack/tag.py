# -*- coding: utf-8 -*-
# jack.tag: name information (ID3 among others) stuff for
# jack - tag audio from a CD and encode it using 3rd party software
# Copyright (C) 1999-2003  Arne Zellentin <zarne@users.sf.net>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import sys
import re

import jack.functions
import jack.ripstuff
import jack.targets
import jack.helpers
import jack.metadata
import jack.utils
import jack.misc
import jack.m3u

from jack.init import oggvorbis
from jack.init import mp3
from jack.init import id3
from jack.init import flac
from jack.init import mp4
from jack.globals import *

track_names = None
mb_query_data = None

a_artist = None
a_title = None


def tag(metadata_rename):
    global a_artist, a_title

    medium_position = 0
    medium_count = 0
    medium_tagging = False

    ext = jack.targets.targets[jack.helpers.helpers[cf['_encoder']]['target']]['file_extension']

    if cf['_vbr'] and not cf['_only_dae']:
        total_length = 0
        total_size = 0
        for i in jack.ripstuff.all_tracks_todo_sorted:
            total_length = total_length + i[LEN]
            total_size = total_size + jack.utils.filesize(i[NAME] + ext)

    if cf['_set_tag'] and not jack.targets.targets[jack.helpers.helpers[cf['_encoder']]['target']]['can_posttag']:
        cf['_set_tag'] = 0

    if jack.metadata.names_available:
        a_artist = track_names[0][0]
        a_title = track_names[0][1]
        medium_position = track_names[0][4]
        medium_count = track_names[0][5]

        if medium_count == -1 or medium_count > 1:
            medium_tagging = True
            if medium_count == -1:
                medium_count = 0

    all_targets = []
    for helper_key, helper_values in jack.helpers.helpers.items():
        if helper_values['type'] == 'encoder':
            target = helper_values['target']
            if target not in all_targets:
                all_targets.append(target)

    if cf['_set_tag'] or metadata_rename:
        jack.m3u.init()
        # use metadata year and genre data if available
        if cf['_year'] == None and len(track_names[0]) >= 3:
            cf['_year'] = track_names[0][2]
        if cf['_genre'] == None and len(track_names[0]) == 4:
            cf['_genre'] = track_names[0][3]
        if cf['_genre']:
            cf['_genre'] = fix_genre_case(cf['_genre'])

        print("Tagging", end=' ')
        for i in jack.ripstuff.all_tracks_todo_sorted:
            sys.stdout.write(".")
            sys.stdout.flush()

            track_position = i[NUM]
            track_count = len(jack.ripstuff.all_tracks_orig)

            all_exts = [ext,]
            for check_ext in all_targets:
                check_ext = "." + check_ext
                if check_ext == ext:
                    continue
                encname = i[NAME] + check_ext
                if os.path.exists(encname):
                    all_exts.append(check_ext)
            
            for cur_ext in all_exts:
                target = cur_ext[1:]
                encname = i[NAME] + cur_ext
                wavname = i[NAME] + ".wav"
                if track_names[i[NUM]][0]:
                    t_artist = track_names[i[NUM]][0]
                else:
                    t_artist = a_artist
                t_name = track_names[i[NUM]][1]
                if not cf['_only_dae'] and cf['_set_tag']:
                    if target == "mp3":
                        m = mp3.MP3(encname)
                        if m.tags == None:
                            m.add_tags()
                        for tag in list(m.tags):
                            key = tag[:4]
                            if key != "APIC":
                                m.tags.delall(key)
                        if cf['_set_extended_tag'] and mb_query_data:
                            extended_tag(m.tags, "id3v2.4", track_position)
                        else:
                            # basic tagging
                            if not cf['_various']:
                                m.tags.add(id3.TPE2(encoding=3, text=a_artist))
                            m.tags.add(id3.TPE1(encoding=3, text=t_artist))
                            m.tags.add(id3.TALB(encoding=3, text=a_title))
                            m.tags.add(id3.TIT2(encoding=3, text=t_name))
                            if cf['_genre']:
                                m.tags.add(id3.TCON(encoding=3, text=cf['_genre']))
                            if cf['_year']:
                                m.tags.add(id3.TDRC(encoding=3, text=cf['_year']))
                            track_info = "%s/%s" % (track_position, track_count)
                            m.tags.add(id3.TRCK(encoding=3, text=track_info))
                            medium_info = "%s/%s" % (medium_position, medium_count)
                            if medium_tagging:
                                m.tags.add(id3.TPOS(encoding=3, text=medium_info))
                        m.save()
                    elif target == "flac" or target == "ogg":   # both vorbis tags
                        if target == "flac":
                            m = flac.FLAC(encname)
                        elif target == "ogg":
                            m = oggvorbis.OggVorbis(encname)
                        if m.tags == None:
                            m.add_vorbiscomment()
                        m.delete() # delete old tags
                        if cf['_set_extended_tag'] and mb_query_data:
                            extended_tag(m.tags, "vorbis", track_position)
                        else:
                            # basic tagging
                            if not cf['_various']:
                                m.tags['ALBUMARTIST'] = a_artist
                            m.tags['ARTIST'] = t_artist
                            m.tags['ALBUM'] = a_title
                            m.tags['TITLE'] = t_name
                            if cf['_genre']:
                                m.tags['GENRE'] = cf['_genre']
                            if cf['_year']:
                                m.tags['DATE'] = cf['_year']
                            m.tags['TRACKNUMBER'] = str(track_position)
                            m.tags['TRACKTOTAL'] = str(track_count)
                            if medium_tagging:
                                m.tags['DISCNUMBER'] = str(medium_position)
                                if medium_count:
                                    m.tags['DISCTOTAL'] = str(medium_count)
                            if cf['_various']:
                                m.tags['COMPILATION'] = "1"
                        m.save()
                    elif target == "m4a":
                        m = mp4.MP4(encname)
                        # delete old tags
                        keeptags = ['©too', '----:com.apple.iTunes:iTunSMPB'] # set by fdkaac
                        for tag in list(m.tags):
                            if tag not in keeptags:
                                m.tags.pop(tag)
                        if cf['_set_extended_tag'] and mb_query_data:
                            extended_tag(m.tags, "mp4", track_position)
                        else:
                            # basic tagging
                            if not cf['_various']:
                                m.tags['aART'] = [a_artist]
                            m.tags['©ART'] = [t_artist]
                            m.tags['©alb'] = [a_title]
                            m.tags['©nam'] = [t_name]
                            if cf['_genre']:
                                m.tags['©gen'] = [cf['_genre']]
                            if cf['_year']:
                                m.tags['©day'] = [cf['_year']]
                            m.tags['trkn'] = [(track_position, track_count)]
                            if medium_tagging:
                                m.tags['disk'] = [(medium_position, medium_count)]
                            m.tags['cpil'] = bool(cf['_various'])
                        m.save()
            if metadata_rename:
                newname = jack.metadata.filenames[i[NUM]]
                encname = i[NAME] + ext
                if i[NAME] != newname:
                    p_newname = newname
                    u_newname = newname
                    newname = newname
                    p_encname = i[NAME]
                    p_wavname = i[NAME]
                    ok = 1
                    if os.path.exists(newname + ext):
                        ok = 0
                        print('NOT renaming "' + p_encname + '" to "' + p_newname + ext + '" because dest. exists.')
                        if cf['_keep_wavs']:
                            print('NOT renaming "' + p_wavname + '" to "' + p_newname + ".wav" + '" because dest. exists.')
                    elif cf['_keep_wavs'] and os.path.exists(newname + ".wav"):
                        ok = 0
                        print('NOT renaming "' + p_wavname + '" to "' + p_newname + ".wav" + '" because dest. exists.')
                        print('NOT renaming "' + p_encname + '" to "' + p_newname + ext + '" because WAV dest. exists.')
                    if ok:
                        if not cf['_only_dae']:
                            try:
                                os.rename(encname, newname + ext)
                            except OSError:
                                error('Cannot rename "%s" to "%s" (Filename is too long or has unusable characters)' % (p_encname, p_newname + ext))
                            jack.m3u.add(newname + ext)
                        if cf['_keep_wavs']:
                            os.rename(wavname, newname + ".wav")
                            jack.m3u.add_wav(newname + ".wav")
                        for t in all_targets:
                            e = "." + t
                            if e != ext:
                                othername = i[NAME] + e
                                if os.path.exists(othername):
                                    if os.path.exists(newname + e):
                                        print('NOT renaming "' + othername + '" to "' + newname + e + '" because dest. exists.')
                                    else:
                                        os.rename(othername, newname + e)
                        jack.functions.progress(i[NUM], "ren", "%s-->%s" % (i[NAME], u_newname))
                    elif cf['_silent_mode']:
                        jack.functions.progress(i[NUM], "err", "while renaming track")
        print()

    if not cf['_silent_mode']:
        if jack.metadata.names_available:
            print("Done with \"" + a_artist + " - " + a_title + "\".")
        else:
            print("All done.", end=' ')
        if cf['_set_tag'] and cf['_year']:
            print("Year: %s" % cf['_year'])
        if cf['_set_tag'] and cf['_genre']:
            print("Genre: %s" % cf['_genre'])
        if cf['_vbr'] and not cf['_only_dae']:
            print("Avg. bitrate: %03.0fkbit" % ((total_size * 0.008) / (total_length / 75)))
        else:
            print()

    if jack.m3u.m3u:
        os.environ["JACK_JUST_ENCODED"] = "\n".join(jack.m3u.m3u)
    if jack.m3u.wavm3u:
        os.environ["JACK_JUST_RIPPED"] = "\n".join(jack.m3u.wavm3u)
    jack.m3u.write()

def fix_genre_case(genre):

    from mutagen._constants import GENRES

    for id3genre in GENRES:
        if genre.upper() == id3genre.upper():
            return id3genre
    return genre


def extended_tag(tag_obj, tag_type, track_position):

    # taken from https://picard.musicbrainz.org/docs/mappings/
    mb_tag_map = [
        {
                # part of basic tagging
                "internalname": "album",
                "name": "Album",
                "id3v2.4": "TALB",
                "vorbis": "ALBUM",
                "mp4": "©alb",
                "mbpaths": [["_release_", "title"]]
        },
        {
                "internalname": "albumsort",
                "name": "Album Sort Order",
                "id3v2.4": "TSOA",
                "vorbis": "ALBUMSORT",
                "mp4": "soal",
                "mbpaths": [["_release_", "sort-name"]]
        },
        {
                # part of basic tagging
                "internalname": "title",
                "name": "Track Title",
                "id3v2.4": "TIT2",
                "vorbis": "TITLE",
                "mp4": "©nam",
                "mbpaths": [
                        ["_track_", "title"],
                        ["_track_", "recording", "title"],
                ]
        },
        {
                "internalname": "titlesort",
                "name": "Track Title Sort Order",
                "id3v2.4": "TSOT",
                "vorbis": "TITLESORT",
                "mp4": "sonm",
                "mbpaths": [["_track_", "recording", "sort-name"]]
        },
        {
                "internalname": "work",
                "name": "Work Title",
                "id3v2.4": "TIT1",
                "vorbis": "WORK",
                "mp4": "©wrk",
        },
        {
                # part of basic tagging
                "internalname": "artist",
                "name": "Artist",
                "id3v2.4": "TPE1",
                "vorbis": "ARTIST",
                "mp4": "©ART",
                "mbpaths": [
                        ["_track_", "artist-credit-phrase"],
                        ["_track_", "artist-credit", "_concatenate_", "artist", "name"],
                        ["_track_", "recording", "artist-credit-phrase"],
                        ["_track_", "recording", "artist-credit", "_concatenate_", "artist", "name"],
                ]
        },
        {
                "internalname": "artistsort",
                "name": "Artist Sort Order",
                "id3v2.4": "TSOP",
                "vorbis": "ARTISTSORT",
                "mp4": "soar",
                "mbpaths": [
                        ["_track_", "artist-credit", "_concatenate_", "artist", "sort-name"],
                        ["_track_", "recording", "artist-credit", "_concatenate_", "artist", "sort-name"],
                ]
        },
        {
                # part of basic tagging, using equivalent of ["_release_", "artist-credit-phrase"]
                "internalname": "albumartist",
                "name": "Album Artist",
                "id3v2.4": "TPE2",
                "vorbis": "ALBUMARTIST",
                "mp4": "aART",
                "mbpaths": [
                        ["_release_", "artist-credit-phrase"],
                        ["_release_", "artist-credit", "_concatenate_", "artist", "name"],
                ]
        },
        {
                "internalname": "albumartistsort",
                "name": "Album Artist Sort Order",
                "id3v2.4": "TSO2",
                "vorbis": "ALBUMARTISTSORT",
                "mp4": "soaa",
                "mbpaths": [["_release_", "artist-credit", "_concatenate_", "artist", "sort-name"]]
        },
        {
                "internalname": "artists",
                "name": "Artists",
                "id3v2.4": "TXXX:Artists",
                "vorbis": "ARTISTS",
                "mp4": "----:com.apple.iTunes:ARTISTS",
                "mbpaths": [
                        ["_track_", "artist-credit", "_multiple_", "name"],
                        ["_track_", "artist-credit", "_multiple_", "artist", "name"],
                        ["_track_", "recording", "artist-credit", "_multiple_", "name"],
                        ["_track_", "recording", "artist-credit", "_multiple_", "artist", "name"],
                ]
        },
        {
                # part of basic tagging
                "internalname": "date",
                "name": "Release Date",
                "id3v2.4": "TDRC",
                "vorbis": "DATE",
                "mp4": "©day",
                "mbpaths": [["_release_", "date"]]
        },
        {
                "internalname": "originalalbum",
                "name": "Original Album",
                "id3v2.4": "TOAL",
                "vorbis": None,
                "mp4": None,
                "mbpaths": [["_release_", "release-group", "title"]]
        },
        {
                "internalname": "originalartist",
                "name": "Original Artist",
                "id3v2.4": "TOPE",
                "vorbis": None,
                "mp4": None,
                "mbpaths": [["_release_", "release-group", "artist-credit", "_concatenate_", "artist", "name"]]
        },
        {
                "internalname": "originaldate",
                "name": "Original Release Date",
                "id3v2.4": "TDOR",
                "vorbis": "ORIGINALDATE",
                "mp4": "----:com.apple.iTunes:ORIGINALDATE",
                "mbpaths": [["_release_", "release-group", "first-release-date"]]
        },
        {
                "internalname": "originalyear",
                "name": "Original Release Year",
                "id3v2.4": "TXXX:originalyear",
                "id3-frametype": "TimeStampTextFrame",
                "vorbis": "ORIGINALYEAR",
                "mp4": "----:com.apple.iTunes:ORIGINALYEAR",
                "mbpaths": [["_release_", "release-group", "first-release-date", "_year_from_date_"]]
        },
        {
                "internalname": "originalfilename",
                "name": "Original Filename",
                "id3v2.4": "TOFN",
                "vorbis": "ORIGINALFILENAME",
                "mp4": None,
        },
        {
                "internalname": "composer",
                "name": "Composer",
                "id3v2.4": "TCOM",
                "vorbis": "COMPOSER",
                "vorbis-fmt": "%s",
                "mp4": "©wrt",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "composer", "_multiple_"]]
        },
        {
                "internalname": "composersort",
                "name": "Composer Sort Order",
                "id3v2.4": "TSOC",
                "vorbis": "COMPOSERSORT",
                "vorbis-fmt": "%s",
                "mp4": "soco",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "composer-sort", "_multiple_"]]
        },
        {
                "internalname": "lyricist",
                "name": "Lyricist",
                "id3v2.4": "TEXT",
                "vorbis": "LYRICIST",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:LYRICIST",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "lyricist", "_multiple_"]]
        },
        {
                "internalname": "writer",
                "name": "Writer",
                "id3v2.4": "TXXX:Writer",
                "vorbis": "WRITER",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:WRITER",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "writer", "_multiple_"]]
        },
        {
                "internalname": "conductor",
                "name": "Conductor",
                "id3v2.4": "TPE3",
                "vorbis": "CONDUCTOR",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:CONDUCTOR",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "conductor", "_multiple_"]]
        },
        {
                "internalname": "performer:instrument",
                "name": "Performer [instrument]",
                "id3v2.4": "TMCL",
                "id3-frametype": "PairedTextFrame",
                "vorbis": "PERFORMER",
                "vorbis-fmt": "%s (%s)",
                "mp4": None,
                "mbpaths": [["_release_", "performer", "_multiple_"]]
        },
        {
                "internalname": "remixer",
                "name": "Remixer",
                "id3v2.4": "TPE4",
                "vorbis": "REMIXER",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:REMIXER",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "remixer", "_multiple_"]]
        },
        {
                "internalname": "arranger",
                "name": "Arranger",
                "id3v2.4": "TIPL:arranger",
                "id3-frametype": "PairedTextFrame",
                "vorbis": "ARRANGER",
                "vorbis-fmt": "%s",
                "mp4": None,
                "mbpaths": [["_release_", "related", "arranger", "_multiple_"]]
        },
        {
                "internalname": "engineer",
                "name": "Engineer",
                "id3v2.4": "TIPL:engineer",
                "id3-frametype": "PairedTextFrame",
                "vorbis": "ENGINEER",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:ENGINEER",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "engineer", "_multiple_"]]
        },
        {
                "internalname": "producer",
                "name": "Producer",
                "id3v2.4": "TIPL:producer",
                "id3-frametype": "PairedTextFrame",
                "vorbis": "PRODUCER",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:PRODUCER",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "producer", "_multiple_"]]
        },
        {
                "internalname": "djmixer",
                "name": "Mix-DJ",
                "id3v2.4": "TIPL:DJ-mix",
                "id3-frametype": "PairedTextFrame",
                "vorbis": "DJMIXER",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:DJMIXER",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "mix-DJ", "_multiple_"]]
        },
        {
                "internalname": "mixer",
                "name": "Mixer",
                "id3v2.4": "TIPL:mix",
                "id3-frametype": "PairedTextFrame",
                "vorbis": "MIXER",
                "vorbis-fmt": "%s",
                "mp4": "----:com.apple.iTunes:MIXER",
                "mp4-fmt": "%s",
                "mbpaths": [["_release_", "related", "mix", "_multiple_"]]
        },
        {
                "internalname": "label",
                "name": "Record Label",
                "id3v2.4": "TPUB",
                "vorbis": "LABEL",
                "mp4": "----:com.apple.iTunes:LABEL",
                "mbpaths": [["_release_", "label-info-list", "_multiple_", "label", "name"]]
        },
        {
                "internalname": "movement",
                "name": "Movement",
                "id3v2.4": "MVNM",
                "vorbis": "MOVEMENTNAME",
                "mp4": "©mvn",
        },
        {
                "internalname": "movementnumber",
                "name": "Movement Number",
                "id3v2.4": "MVIN",
                "vorbis": "MOVEMENT",
                "mp4": "mvi",
        },
        {
                "internalname": "movementtotal",
                "name": "Movement Count",
                "id3v2.4": "MVIN",
                "vorbis": "MOVEMENTTOTAL",
                "mp4": "mvc",
        },
        {
                "internalname": "showmovement",
                "name": "Show Work & Movement",
                "id3v2.4": "TXXX:SHOWMOVEMENT",
                "vorbis": "SHOWMOVEMENT",
                "mp4": "shwm",
        },
        {
                "internalname": "grouping",
                "name": "Grouping",
                "id3v2.4": "GRP1",
                "vorbis": "GROUPING",
                "mp4": "©grp",
        },
        {
                "internalname": "subtitle",
                "name": "Subtitle",
                "id3v2.4": "TIT3",
                "vorbis": "SUBTITLE",
                "mp4": "----:com.apple.iTunes:SUBTITLE",
        },
        {
                "internalname": "discsubtitle",
                "name": "Disc Subtitle",
                "id3v2.4": "TSST",
                "vorbis": "DISCSUBTITLE",
                "mp4": "----:com.apple.iTunes:DISCSUBTITLE",
                "mbpaths": [["_medium_", "title"]]
        },
        {
                # part of basic tagging
                "internalname": "tracknumber",
                "name": "Track Number",
                "id3v2.4": "TRCK",
                "id3-frametype": "NumericPartTextFrame",
                "vorbis": "TRACKNUMBER",
                "mp4": "trkn",
                "mp4-type": "tuple",
                "tuple-position": 0,
                "mbpaths": [["_track_", "position"]]
        },
        {
                # part of basic tagging
                "internalname": "totaltracks",
                "name": "Total Tracks",
                "id3v2.4": "TRCK",
                "id3-frametype": "NumericPartTextFrame",
                "vorbis": "TRACKTOTAL",
                "mp4": "trkn",
                "mp4-type": "tuple",
                "tuple-position": 1,
                "mbpaths": [["_medium_", "track-count"]]
        },
        {
                # part of basic tagging
                "internalname": "discnumber",
                "name": "Disc Number",
                "id3v2.4": "TPOS",
                "id3-frametype": "NumericPartTextFrame",
                "vorbis": "DISCNUMBER",
                "mp4": "disk",
                "mp4-type": "tuple",
                "tuple-position": 0,
                "mbpaths": [["_medium_", "position"]]
        },
        {
                # part of basic tagging
                "internalname": "totaldiscs",
                "name": "Total Discs",
                "id3v2.4": "TPOS",
                "id3-frametype": "NumericPartTextFrame",
                "vorbis": "DISCTOTAL",
                "mp4": "disk",
                "mp4-type": "tuple",
                "tuple-position": 1,
                "mbpaths": [["_release_", "medium-count"]]
        },
        {
                # part of basic tagging
                "internalname": "compilation",
                "name": "Compilation (iTunes)",
                "id3v2.4": "TCMP",
                "vorbis": "COMPILATION",
                "mp4": "cpil",
                "mp4-type": "boolean",
                "mbpaths": [["_compilation_"]]
        },
        {
                "internalname": "comment:description",
                "name": "Comment",
                "id3v2.4": "COMM:description",
                "vorbis": "COMMENT",
                "mp4": "©cmt",
        },
        {
                # part of basic tagging
                "internalname": "genre",
                "name": "Genre",
                "id3v2.4": "TCON",
                "vorbis": "GENRE",
                "mp4": "©gen",
                "mbpaths": [["_genre_"]]
        },
        {
                "internalname": "_rating",
                "name": "Rating",
                "id3v2.4": "POPM",
                "vorbis": "RATING:user@email",
                "mp4": None,
        },
        {
                "internalname": "bpm",
                "name": "BPM",
                "id3v2.4": "TBPM",
                "vorbis": "BPM",
                "mp4": "tmpo",
        },
        {
                "internalname": "mood",
                "name": "Mood",
                "id3v2.4": "TMOO",
                "vorbis": "MOOD",
                "mp4": "----:com.apple.iTunes:MOOD",
        },
        {
                "internalname": "lyrics:description",
                "name": "Lyrics",
                "id3v2.4": "USLT:description",
                "vorbis": "LYRICS",
                "mp4": "©lyr",
        },
        {
                "internalname": "media",
                "name": "Media",
                "id3v2.4": "TMED",
                "vorbis": "MEDIA",
                "mp4": "----:com.apple.iTunes:MEDIA",
                "mbpaths": [["_medium_", "format"]]
        },
        {
                "internalname": "catalognumber",
                "name": "Catalog Number",
                "id3v2.4": "TXXX:CATALOGNUMBER",
                "vorbis": "CATALOGNUMBER",
                "mp4": "----:com.apple.iTunes:CATALOGNUMBER",
                "mbpaths": [["_release_", "label-info-list", "_multiple_", "catalog-number"]]
        },
        {
                "internalname": "show",
                "name": "Show Name",
                "id3v2.4": None,
                "vorbis": None,
                "mp4": "tvsh",
        },
        {
                "internalname": "showsort",
                "name": "Show Name Sort Order",
                "id3v2.4": None,
                "vorbis": None,
                "mp4": "sosn",
        },
        {
                "internalname": "podcast",
                "name": "Podcast",
                "id3v2.4": None,
                "vorbis": None,
                "mp4": "pcst",
        },
        {
                "internalname": "podcasturl",
                "name": "Podcast URL",
                "id3v2.4": None,
                "vorbis": None,
                "mp4": "purl",
        },
        {
                "internalname": "releasestatus",
                "name": "Release Status",
                "id3v2.4": "TXXX:MusicBrainz Album Status",
                "vorbis": "RELEASESTATUS",
                "mp4": "----:com.apple.iTunes:MusicBrainz Album Status",
                "mbpaths": [["_release_", "status", "_tolowercase_"]]
        },
        {
                "internalname": "releasetype",
                "name": "Release Type",
                "id3v2.4": "TXXX:MusicBrainz Album Type",
                "vorbis": "RELEASETYPE",
                "mp4": "----:com.apple.iTunes:MusicBrainz Album Type",
                "mbpaths": [
                        ["_release_", "release-group", "primary-type", "_tolowercase_", "_append_next_"],
                        ["_release_", "release-group", "secondary-type-list", "_multiple_", "_tolowercase_"],
                ]
        },
        {
                "internalname": "releasecountry",
                "name": "Release Country",
                "id3v2.4": "TXXX:MusicBrainz Album Release Country",
                "vorbis": "RELEASECOUNTRY",
                "mp4": "----:com.apple.iTunes:MusicBrainz Album Release Country",
                "mbpaths": [["_release_", "country"]]
        },
        {
                "internalname": "script",
                "name": "Script",
                "id3v2.4": "TXXX:SCRIPT",
                "vorbis": "SCRIPT",
                "mp4": "----:com.apple.iTunes:SCRIPT",
                "mbpaths": [["_release_", "text-representation", "script"]]
        },
        {
                "internalname": "language",
                "name": "Language",
                "id3v2.4": "TLAN",
                "vorbis": "LANGUAGE",
                "mp4": "----:com.apple.iTunes:LANGUAGE",
                "mbpaths": [["_release_", "text-representation", "language"]]
        },
        {
                "internalname": "copyright",
                "name": "Copyright",
                "id3v2.4": "TCOP",
                "vorbis": "COPYRIGHT",
                "mp4": "cprt",
        },
        {
                "internalname": "license",
                "name": "License",
                "id3v2.4": "WCOP",
                "vorbis": "LICENSE",
                "mp4": "----:com.apple.iTunes:LICENSE",
        },
        {
                # handled by encoder
                "internalname": "encodedby",
                "name": "Encoded By",
                "id3v2.4": "TENC",
                "vorbis": "ENCODEDBY",
                "mp4": "©too",
        },
        {
                # handled by encoder
                "internalname": "encodersettings",
                "name": "Encoder Settings",
                "id3v2.4": "TSSE",
                "vorbis": "ENCODERSETTINGS",
                "mp4": None,
        },
        {
                "internalname": "gapless",
                "name": "Gapless Playback",
                "id3v2.4": None,
                "vorbis": None,
                "mp4": "pgap",
        },
        {
                "internalname": "barcode",
                "name": "Barcode",
                "id3v2.4": "TXXX:BARCODE",
                "vorbis": "BARCODE",
                "mp4": "----:com.apple.iTunes:BARCODE",
                "mbpaths": [["_release_", "barcode"]]
        },
        {
                "internalname": "isrc",
                "name": "ISRC",
                "id3v2.4": "TSRC",
                "vorbis": "ISRC",
                "mp4": "----:com.apple.iTunes:ISRC",
                "mbpaths": [["_track_", "recording", "isrc-list", "_multiple_"]]
        },
        {
                "internalname": "asin",
                "name": "ASIN",
                "id3v2.4": "TXXX:ASIN",
                "vorbis": "ASIN",
                "mp4": "----:com.apple.iTunes:ASIN",
                "mbpaths": [["_release_", "asin"]]
        },
        {
                "internalname": "musicbrainz_recordingid",
                "name": "MusicBrainz Recording Id",
                "id3v2.4": "UFID:http://musicbrainz.org",
                "vorbis": "MUSICBRAINZ_TRACKID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Track Id",
                "mbpaths": [["_track_", "recording", "id"]]
        },
        {
                "internalname": "musicbrainz_trackid",
                "name": "MusicBrainz Track Id",
                "id3v2.4": "TXXX:MusicBrainz Release Track Id",
                "vorbis": "MUSICBRAINZ_RELEASETRACKID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Release Track Id",
                "mbpaths": [["_track_", "id"]]
        },
        {
                "internalname": "musicbrainz_albumid",
                "name": "MusicBrainz Release Id",
                "id3v2.4": "TXXX:MusicBrainz Album Id",
                "vorbis": "MUSICBRAINZ_ALBUMID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Album Id",
                "mbpaths": [["_release_", "id"]]
        },
        {
                "internalname": "musicbrainz_originalalbumid",
                "name": "MusicBrainz Original Release Id",
                "id3v2.4": "TXXX:MusicBrainz Original Album Id",
                "vorbis": "MUSICBRAINZ_ORIGINALALBUMID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Original Album Id",
        },
        {
                "internalname": "musicbrainz_artistid",
                "name": "MusicBrainz Artist Id",
                "id3v2.4": "TXXX:MusicBrainz Artist Id",
                "vorbis": "MUSICBRAINZ_ARTISTID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Artist Id",
                "mbpaths": [
                        ["_track_", "artist-credit", "_multiple_", "artist", "id"],
                        ["_track_", "recording", "artist-credit", "_multiple_", "artist", "id"],
                ]
        },
        {
                "internalname": "musicbrainz_originalartistid",
                "name": "MusicBrainz Original Artist Id",
                "id3v2.4": "TXXX:MusicBrainz Original Artist Id",
                "vorbis": "MUSICBRAINZ_ORIGINALARTISTID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Original Artist Id",
        },
        {
                "internalname": "musicbrainz_albumartistid",
                "name": "MusicBrainz Release Artist Id",
                "id3v2.4": "TXXX:MusicBrainz Album Artist Id",
                "vorbis": "MUSICBRAINZ_ALBUMARTISTID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Album Artist Id",
                "mbpaths": [["_release_", "artist-credit", "_multiple_", "artist", "id"]]
        },
        {
                "internalname": "musicbrainz_releasegroupid",
                "name": "MusicBrainz Release Group Id",
                "id3v2.4": "TXXX:MusicBrainz Release Group Id",
                "vorbis": "MUSICBRAINZ_RELEASEGROUPID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Release Group Id",
                "mbpaths": [["_release_", "release-group", "id"]]
        },
        {
                "internalname": "musicbrainz_workid",
                "name": "MusicBrainz Work Id",
                "id3v2.4": "TXXX:MusicBrainz Work Id",
                "vorbis": "MUSICBRAINZ_WORKID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Work Id",
        },
        {
                "internalname": "musicbrainz_trmid",
                "name": "MusicBrainz TRM Id",
                "id3v2.4": "TXXX:MusicBrainz TRM Id",
                "vorbis": "MUSICBRAINZ_TRMID",
                "mp4": "----:com.apple.iTunes:MusicBrainz TRM Id",
        },
        {
                "internalname": "musicbrainz_discid",
                "name": "MusicBrainz Disc Id",
                "id3v2.4": "TXXX:MusicBrainz Disc Id",
                "vorbis": "MUSICBRAINZ_DISCID",
                "mp4": "----:com.apple.iTunes:MusicBrainz Disc Id",
                "mbpaths": [["_disc_id_"]]
        },
        {
                "internalname": "acoustid_id",
                "name": "AcoustID",
                "id3v2.4": "TXXX:Acoustid Id",
                "vorbis": "ACOUSTID_ID",
                "mp4": "----:com.apple.iTunes:Acoustid Id",
        },
        {
                "internalname": "acoustid_fingerprint",
                "name": "AcoustID Fingerprint",
                "id3v2.4": "TXXX:Acoustid Fingerprint",
                "vorbis": "ACOUSTID_FINGERPRINT",
                "mp4": "----:com.apple.iTunes:Acoustid Fingerprint",
        },
        {
                "internalname": "musicip_puid",
                "name": "MusicIP PUID",
                "id3v2.4": "TXXX:MusicIP PUID",
                "vorbis": "MUSICIP_PUID",
                "mp4": "----:com.apple.iTunes:MusicIP PUID",
        },
        {
                "internalname": "musicip_fingerprint",
                "name": "MusicIP Fingerprint",
                "id3v2.4": "TXXX:MusicMagic Fingerprint",
                "vorbis": "FINGERPRINT=MusicMagic Fingerprint",
                "mp4": "----:com.apple.iTunes:fingerprint",
        },
        {
                "internalname": "website",
                "name": "Website (official artist website)",
                "id3v2.4": "WOAR",
                "vorbis": "WEBSITE",
                "mp4": None,
        },
        {
                "internalname": "key",
                "name": "Initial key",
                "id3v2.4": "TKEY",
                "vorbis": "KEY",
                "mp4": "----:com.apple.iTunes:initialkey",
        },
        {
                "internalname": "replaygain_album_gain",
                "name": "ReplayGain Album Gain",
                "id3v2.4": "TXXX:REPLAYGAIN_ALBUM_GAIN",
                "vorbis": "REPLAYGAIN_ALBUM_GAIN",
                "mp4": "----:com.apple.iTunes:REPLAYGAIN_ALBUM_GAIN",
        },
        {
                "internalname": "replaygain_album_peak",
                "name": "ReplayGain Album Peak",
                "id3v2.4": "TXXX:REPLAYGAIN_ALBUM_PEAK",
                "vorbis": "REPLAYGAIN_ALBUM_PEAK",
                "mp4": "----:com.apple.iTunes:REPLAYGAIN_ALBUM_PEAK",
        },
        {
                "internalname": "replaygain_album_range",
                "name": "ReplayGain Album Range",
                "id3v2.4": "TXXX:REPLAYGAIN_ALBUM_RANGE",
                "vorbis": "REPLAYGAIN_ALBUM_RANGE",
                "mp4": "----:com.apple.iTunes:REPLAYGAIN_ALBUM_RANGE",
        },
        {
                "internalname": "replaygain_track_gain",
                "name": "ReplayGain Track Gain",
                "id3v2.4": "TXXX:REPLAYGAIN_TRACK_GAIN",
                "vorbis": "REPLAYGAIN_TRACK_GAIN",
                "mp4": "----:com.apple.iTunes:REPLAYGAIN_TRACK_GAIN",
        },
        {
                "internalname": "replaygain_track_peak",
                "name": "ReplayGain Track Peak",
                "id3v2.4": "TXXX:REPLAYGAIN_TRACK_PEAK",
                "vorbis": "REPLAYGAIN_TRACK_PEAK",
                "mp4": "----:com.apple.iTunes:REPLAYGAIN_TRACK_PEAK",
        },
        {
                "internalname": "replaygain_track_range",
                "name": "ReplayGain Track Range",
                "id3v2.4": "TXXX:REPLAYGAIN_TRACK_RANGE",
                "vorbis": "REPLAYGAIN_TRACK_RANGE",
                "mp4": "----:com.apple.iTunes:REPLAYGAIN_TRACK_RANGE",
        },
        {
                "internalname": "replaygain_reference_loudness",
                "name": "ReplayGain Reference Loudness",
                "id3v2.4": "TXXX:REPLAYGAIN_REFERENCE_LOUDNESS",
                "vorbis": None,
                "mp4": None,
        }
    ]

    if not cf['_set_extended_tag']:
        print("no extended tagging wanted")
        return
    if not mb_query_data:
        print("no extended metadata available")
        return

    # prepare data
    chosen_release = mb_query_data['chosen_release']
    genre = mb_query_data['genre']
    disc_id = mb_query_data['result']['disc']['id']
    release = mb_query_data['result']['disc']['release-list'][chosen_release]
    medium = None
    for medium_candidate in release['medium-list']:
        for disc_candidate in medium_candidate['disc-list']:
            if disc_candidate['id'] == disc_id:
                medium = medium_candidate
    track = medium['track-list'][track_position - 1]

    # make artist names easier to parse
    if 'artist-credit' in track:
        for ac in track['artist-credit']:
            if not 'name' in ac and 'artist' in ac and 'name' in ac['artist']:
                ac['name'] = ac['artist']['name']

    # make performers easier to parse
    performers = {}
    performer_types = ["instrument", "vocal"]
    if 'artist-relation-list' in release:
        for ar in release['artist-relation-list']:
            if 'artist' in ar and 'name' in ar['artist']:
                performer = ar['artist']['name']
            else:
                continue
            if 'type' in ar and 'attribute-list' in ar and ar['type'] in performer_types:
                for instrument in ar['attribute-list']:
                    if not performer in performers:
                        performers[performer] = [instrument]
                    else:
                        if not instrument in performers[performer]:
                            performers[performer].append(instrument)
            if 'type' in ar and 'attribute-list' not in ar and ar['type'] == "vocal":
                instrument = "vocals"
                if not performer in performers:
                    performers[performer] = [instrument]
                else:
                    if not instrument in performers[performer]:
                        performers[performer].append(instrument)
    release['performer'] = []
    for performer, instruments in performers.items():
        instruments_concatenated = None
        for instrument in instruments:
            if instruments_concatenated:
                instruments_concatenated += " and " + instrument
            else:
                instruments_concatenated = instrument
        release['performer'].append((performer, instruments_concatenated))

    # make mixers, producers easier to parse
    release['related'] = {}
    related = release['related']
    if 'artist-relation-list' in release:
        for ar in release['artist-relation-list']:
            if 'artist' in  ar and 'type' in ar['artist'] and ar['artist']['type'] != "Other":
                if 'type' in ar and 'name' in ar['artist']:
                    ar_type = ar['type']
                    if not ar_type in related:
                        related[ar_type] = []
                    related[ar_type].append((ar['artist']['name'],))
                if 'type' in ar and 'sort-name' in ar['artist']:
                    ar_type = ar['type'] + "-sort"
                    if not ar_type in related:
                        related[ar_type] = []
                    related[ar_type].append((ar['artist']['sort-name'],))

    # parse data using tag map
    paired_tags={}
    tipl_list = []
    for map_entry in mb_tag_map:
        if not 'mbpaths' in map_entry:
            continue
        if not map_entry[tag_type]:
            continue
        mbpaths = map_entry['mbpaths']

        built_paths = []
        mbpath_try = 0
        for mbpath in mbpaths:
            built_path = None
            depth = 0
            break_after_success = True
            for item in mbpath:
                if item[:1] == '_' and item[-1:] == '_':
                    if item == "_release_":
                        built_path = release
                    elif item == "_medium_":
                        built_path = medium
                    elif item == "_track_":
                        built_path = track
                    elif item == "_disc_id_":
                        built_path = disc_id
                    elif item == "_compilation_":
                        if cf['_various']:
                            built_path = "1"
                        else:
                            built_path = None
                    elif item == "_genre_":
                        built_path = genre
                    elif item == "_concatenate_":
                        concat_string = ""
                        concat_path = mbpath[depth+1:]
                        # concatenate dicts and strings
                        for next_item in built_path:
                            if isinstance(next_item, str):
                                concat_string += next_item
                            elif isinstance(next_item, dict):
                                for key, value in next_item.items():
                                    if key == concat_path[0]:
                                        sub_path = next_item
                                        for sub_item in concat_path:
                                            if sub_item in sub_path:
                                                sub_path = sub_path[sub_item]
                                        concat_string += sub_path
                        built_path = concat_string
                        break
                    elif item == "_multiple_":
                        remain_items = mbpath[depth+1:]
                        if built_path:
                            multi_built_path = None
                            for multi_path in built_path:
                                if isinstance(built_path[0], str) and isinstance(multi_path, str):
                                    multi_built_path = multi_path
                                    if remain_items and len(remain_items) and remain_items[0] == "_tolowercase_":
                                        multi_built_path = multi_built_path.lower()
                                if isinstance(built_path[0], tuple):
                                    multi_built_path = multi_path
                                if isinstance(multi_path, dict):
                                    multi_built_path = multi_path
                                    for rem_item in remain_items:
                                        if multi_built_path and rem_item in multi_built_path:
                                            multi_built_path = multi_built_path[rem_item]
                                        else:
                                            multi_built_path = None
                                if multi_built_path and multi_built_path not in built_paths:
                                    built_paths.append(multi_built_path)
                        built_path = None
                    elif item == "_tolowercase_":
                        if built_path:
                            built_path = built_path.lower()
                    elif item == "_year_from_date_":
                        built_path = built_path[:4]
                    elif item == "_append_next_":
                        break_after_success = False
                    else:
                        print("unknown special item", item)
                        built_path = None
                else:
                    if built_path and item in built_path:
                        built_path = built_path[item]
                    else:
                        built_path = None
                depth += 1
            if built_path:
                if isinstance(built_path, str) or isinstance(built_path, int) or isinstance(built_path, tuple):
                    built_paths.append(built_path)
                else:
                    error("built_path is not a string or an in for " + map_entry['name'])
            
            if len(built_paths):
                if len(mbpaths) > 1:
                    if break_after_success:
                        break
            mbpath_try += 1

        i = 0
        built_path_concat = []

        for built_path in built_paths:
            debug(tag_type + " tagging" + map_entry['name'] +  "-->" + str(built_path))

            # track numbers and disc numbers need to be paired in mp4 and id3v2.4 tags
            if 'tuple-position' in map_entry:
                tuple_position = map_entry['tuple-position']
                if not map_entry[tag_type] in paired_tags:
                    paired_tags[map_entry[tag_type]] = [0, 0]
                paired_tags[map_entry[tag_type]][tuple_position] = int(built_path)

            if tag_type == "vorbis":
                if 'vorbis-fmt' in map_entry:
                    built_path = map_entry['vorbis-fmt'] % built_path
                tag_obj.append([map_entry[tag_type], str(built_path)])
            elif tag_type == "id3v2.4":
                if isinstance(built_path, str):
                    built_path_concat.append(built_path)
                elif isinstance(built_path, tuple):
                    built_path_concat.append(list(reversed(built_path)))
                id3_key = map_entry[tag_type]
                id3_argument = None
                if ':' in id3_key:
                    id3_key, id3_argument = id3_key.split(':', 1)
                frame = None
                id3_frametype = "TextFrame"
                if "id3-frametype" in map_entry:
                    id3_frametype = map_entry['id3-frametype']
                if id3_frametype == "TimeStampTextFrame":
                    frame = id3.Frames[id3_key](encoding=3, text=built_path[:4], desc=id3_argument)
                elif id3_frametype == "NumericPartTextFrame":
                    text = "%s/%s" % tuple(paired_tags[map_entry[tag_type]])
                    frame = id3.Frames[id3_key](encoding=3, text=text)
                elif id3_frametype == "PairedTextFrame":
                    people = built_path_concat
                    if id3_argument:
                        if id3_key == "TIPL":
                            for item in built_path_concat:
                                if not id3_argument in item:
                                    item.insert(0, id3_argument)
                            if not item in tipl_list:
                                tipl_list.extend([item])
                            people = tipl_list
                    frame = id3.Frames[id3_key](encoding=3, people=people)
                else:
                    if id3_argument:
                        if id3_key == "TXXX":
                            if len(built_path_concat) > 1:
                                frame = id3.Frames[id3_key](encoding=3, text=built_path_concat, desc=id3_argument)
                            else:
                                frame = id3.Frames[id3_key](encoding=3, text=built_path_concat[0], desc=id3_argument)
                        elif id3_key == "UFID":
                            frame = id3.Frames[id3_key](encoding=3, data=built_path_concat[0].encode('utf-8'), owner=id3_argument)
                        else:
                            warning("unexpected argument '" + id3_argument + "' for key '" + id3_key)
                    else:
                        if len(built_path_concat) > 1:
                            frame = id3.Frames[id3_key](encoding=3, text=built_path_concat)
                        elif len(built_path_concat) == 1:
                            frame = id3.Frames[id3_key](encoding=3, text=built_path_concat[0])
                if frame:
                    tag_obj.add(frame)
            elif tag_type == "mp4":
                if 'mp4-fmt' in map_entry:
                    built_path = map_entry['mp4-fmt'] % built_path
                mp4_type = "list-of-strings"
                if "mp4-type" in map_entry:
                    mp4_type = map_entry['mp4-type']
                if mp4_type == "boolean":
                    tag_obj[map_entry[tag_type]] = bool(built_path)
                elif mp4_type == "tuple":
                    if not map_entry[tag_type] in tag_obj:
                        tag_obj[map_entry[tag_type]] = [(0,0)]
                    tag_obj[map_entry[tag_type]][0] = tuple(paired_tags[map_entry[tag_type]])
                else:
                    if map_entry[tag_type][:4] == '----':
                        built_path = mp4.MP4FreeForm(built_path.encode("utf-8"), dataformat=mp4.AtomDataType.UTF8)
                    if not map_entry[tag_type] in tag_obj:
                        tag_obj[map_entry[tag_type]] = []
                    tag_obj[map_entry[tag_type]].append(built_path)
            else:
                error("unknown tag type " + tag_type)
            i+=1
